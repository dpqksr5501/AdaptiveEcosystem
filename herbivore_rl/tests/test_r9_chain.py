"""R9 두뇌 팩·이어 학습 실행기 시험 (클라우드 학습 안내 AdaptiveEcosystem/Docs/RL_Policy/R9_CLOUD_TRAINING.md).

학습은 돌리지 않는다. 가짜 가중치 npz(몸 해시는 진짜 설정)와 가짜 zip 으로 팩 만들기·확인·변조 찾기, 몸이 다른 세계의 rebody,
바퀴별 이어 받기·상대 판 고르기, 끊긴 시도 옮기기, 고정 값 지키기를 본다.
"""

import json
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2 import r9_body as B
from env_v2 import r9_brains as BR

sys.path.insert(0, str(ROOT / "results" / "v3" / "r9"))
import chain_r9 as C  # noqa: E402
import pack_r9 as P  # noqa: E402

CFG = "configs/v3_r9_fauna.yaml"
MCFG = "configs/v3_r9_fauna_motion.yaml"
SP6 = C.SPECIES6


def fake_brain(path, cfg, sp, round_, dec, seed=0):
    rng = np.random.default_rng(seed)
    w = {k: rng.normal(0, 0.1, BR.NPZ_SHAPES[k]).astype(np.float32) for k in BR.NPZ_WEIGHT_KEYS}
    BR.save_brain(path, w, BR.brain_meta(cfg, sp, "t", round_, dec, None))
    path.with_suffix(".zip").write_bytes(f"zip {sp} {round_} {dec}".encode())
    path.with_suffix(".json").write_text("{}", encoding="utf-8")


@pytest.fixture(scope="module")
def cfg():
    return B.load_r9_config(ROOT / CFG)


@pytest.fixture()
def src(tmp_path, cfg):
    d = tmp_path / "src"
    d.mkdir()
    for i, sp in enumerate(SP6):
        fake_brain(d / f"{sp}_r1_1000.npz", cfg, sp, 1, 1000, seed=i)
        fake_brain(d / f"{sp}_r2_2000.npz", cfg, sp, 2, 2000, seed=10 + i)
    return d


def test_pack_make_verify_roundtrip(tmp_path, src):
    man = P.make(src, tmp_path / "packs" / "p1", CFG, None, "last", [], "시험")
    assert sorted(man["species"]) == sorted(SP6)
    assert man["species"]["deer"]["zip"] == "deer/deer_r2_2000.zip"
    assert [v["round"] for v in man["species"]["deer"]["versions"]] == [2]
    r = P.verify(tmp_path / "packs" / "p1", CFG)
    assert r["ok"], r["problems"]
    assert all(s["same_body"] for s in r["species"].values())
    allv = P.make(src, tmp_path / "packs" / "p2", CFG, ["wolf"], "all", [], "")
    assert [v["round"] for v in allv["species"]["wolf"]["versions"]] == [1, 2]
    with pytest.raises(FileExistsError):
        P.make(src, tmp_path / "packs" / "p1", CFG, None, "last", [], "")


def test_pack_verify_finds_tampering(tmp_path, src):
    pk = tmp_path / "p"
    P.make(src, pk, CFG, ["deer"], "last", [], "")
    (pk / "deer" / "deer_r2_2000.zip").write_bytes(b"changed")
    (pk / "stray.txt").write_text("x", encoding="utf-8")
    r = P.verify(pk)
    assert not r["ok"]
    assert any("sha256 다름" in p for p in r["problems"]) and any("stray.txt" in p for p in r["problems"])


def test_pack_refuses_wrong_body(tmp_path, src):
    mcfg = B.load_r9_config(ROOT / MCFG)
    differ = [sp for sp in SP6 if B.body_hash(mcfg, BR._species_index(sp)) != B.body_hash(B.load_r9_config(ROOT / CFG), BR._species_index(sp))]
    assert differ, "M1 설정은 몸 해시가 달라야 한다 (회전 한계가 몸)"
    with pytest.raises(ValueError):
        P.make(src, tmp_path / "p", MCFG, [differ[0]], "last", [], "")
    assert not (tmp_path / "p").exists()                 # 실패하면 반쯤 만든 팩을 남기지 않는다


def test_line_names_and_seed():
    for bad in ("A", "B", "x", "Dots1", "a b", "a" * 25):
        with pytest.raises(SystemExit):
            C.Line("ckpt/r9_cloud", bad)
    assert C.Line("ckpt/r9_cloud", "dots1").snaps.name == "dots1"
    s = C.model_seed_for("dots1")
    assert 100 <= s < 1000 and s == C.model_seed_for("dots1") and s not in (0, 1)


def _args(tmp_path, pack, config=CFG, line="t1", **kw):
    a = C.build_parser().parse_args(["run", "--pack", str(pack), "--config", config, "--line", line, "--out", str(tmp_path / "out")])
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def test_plan_fixed_values(tmp_path, src):
    pk = tmp_path / "pk"
    P.make(src, pk, CFG, None, "last", [], "")
    a = _args(tmp_path, pk)
    line = C.Line(a.out, a.line)
    plan = C.check_plan(line, C.build_plan(a, line), replan=False)
    assert plan["species"] == list(SP6) and plan["model_seed"] == C.model_seed_for("t1")
    again = C.check_plan(line, C.build_plan(_args(tmp_path, pk, rounds=20, wall_hours=1.0), line), replan=False)
    assert again["created"] == plan["created"]           # 바퀴 수·벽시계는 고정 값이 아님
    with pytest.raises(SystemExit):
        C.check_plan(line, C.build_plan(_args(tmp_path, pk, decisions=123), line), replan=False)
    re_ = C.check_plan(line, C.build_plan(_args(tmp_path, pk, decisions=123), line), replan=True)
    assert re_["decisions"] == 123 and re_["replans"][0]["changed"]["decisions"] == [5_000_000, 123]


def test_rebody_start_and_round_inputs(tmp_path, src, cfg):
    pk = tmp_path / "pk"
    P.make(src, pk, CFG, None, "last", [], "")
    a = _args(tmp_path, pk, config=MCFG)
    line = C.Line(a.out, a.line)
    plan = C.check_plan(line, C.build_plan(a, line), replan=False)
    start = C.prepare_start(line, plan, dry=False)
    mcfg = B.load_r9_config(ROOT / MCFG)
    for sp in SP6:
        z, vers = start[sp]
        assert z == pk / sp / f"{sp}_r2_2000.zip"
        BR.load_brain(vers[0], mcfg, sp)                  # M1 세계에서 실린다
    assert C.prepare_start(line, plan, dry=False)[SP6[0]][1] == start[SP6[0]][1]      # 두 번째는 그대로 다시 씀
    # 바퀴 1·2 판을 흉내: 바퀴 2 는 바퀴 1 마지막 zip 에서, 상대는 바퀴 2 앞 판만
    line.snaps.mkdir(parents=True)
    for sp in SP6:
        fake_brain(line.snaps / f"{sp}_r1_500.npz", mcfg, sp, 1, 500)
        fake_brain(line.snaps / f"{sp}_r1_900.npz", mcfg, sp, 1, 900)
        fake_brain(line.snaps / f"{sp}_r2_400.npz", mcfg, sp, 2, 400)
    assert C.last_zip(line, start, "deer", 1) == start["deer"][0]
    assert C.last_zip(line, start, "deer", 2) == line.snaps / "deer_r1_900.zip"
    pool = C.pool_for(line, plan, start, "deer", 2)
    assert "deer" not in pool and len(pool["wolf"]) == 3 and not any("_r2_" in p for p in pool["wolf"])
    cmd = C.train_cmd(line, plan, "wolf", 2, C.last_zip(line, start, "wolf", 2), tmp_path / "pool.json", 2, 1.0)
    assert cmd[cmd.index("--model-seed") + 1] == str(plan["model_seed"]) and cmd[cmd.index("--branch") + 1] == "t1"
    assert cmd[cmd.index("--config") + 1] == MCFG and cmd[cmd.index("--shards") + 1] == "2"


def test_status_and_partial_moves(tmp_path, cfg):
    line = C.Line(str(tmp_path / "out"), "t2")
    line.snaps.mkdir(parents=True)
    assert C.species_status(line, "deer", 1) == "none"
    fake_brain(line.snaps / "deer_r1_100.npz", cfg, "deer", 1, 100)
    assert C.species_status(line, "deer", 1) == "partial"
    meta = line.snaps / f"{line.run_name('deer', 1)}.json"
    meta.write_text(json.dumps({"stop": "cut"}), encoding="utf-8")
    assert C.species_status(line, "deer", 1) == "cut"
    assert C.move_partial(line, "deer", 1, "try1") == 4         # npz·zip·json + 끝 기록
    assert C.species_status(line, "deer", 1) == "none" and (line.partial / "r1_deer_try1" / meta.name).exists()
    meta.write_text(json.dumps({"stop": "wall_clock"}), encoding="utf-8")
    assert C.species_status(line, "deer", 1) == "ok"
    meta.write_text(json.dumps({"stop": "nan"}), encoding="utf-8")
    assert C.species_status(line, "deer", 1) == "error"
    (line.snaps / f"{line.run_name('deer', 1)}.history.json").write_text("{}", encoding="utf-8")
    assert C.run_metas(line, "deer") == [meta]


def test_shards_profiles():
    assert C.shards_for("auto", list(SP6), 20, 16.0) == C.SHARDS_FULL
    assert C.shards_for("auto", list(SP6), 4, 16.0) == {sp: 1 for sp in SP6}
    assert C.shards_for("auto", list(SP6), 20, 2.0) == {sp: 1 for sp in SP6}
    assert C.shards_for("3", ["wolf"], 4, None) == {"wolf": 3}
    assert C.shards_for('{"wolf": 2}', ["deer", "wolf"], 4, None) == {"deer": 1, "wolf": 2}


def test_committed_start_pack_is_intact():
    pk = ROOT / "results" / "v3" / "r9" / "packs" / "fauna_r2"
    r = P.verify(pk, CFG)
    assert r["ok"], r["problems"]
    assert sorted(r["species"]) == sorted(SP6) and all(s["same_body"] for s in r["species"].values())
