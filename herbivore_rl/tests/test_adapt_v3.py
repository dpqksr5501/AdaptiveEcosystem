"""적응 고리 도구 results/v3/adapt/adapt.py (10-18 사용자 '… 가중치 로더 써서 두뇌 바꿔 주는 기술을 한번 적용해 보자. 바뀌는 환경에 맞는 적응을 시키는 거지').

- 변환: 저장소의 언리얼 스냅숏(세션 20003, 통합 레벨 기본값)은 바탕 거울 설정과 바뀐 칸이 하나도 없다. 칸을 바꾼 스냅숏은 대응표대로 옮기거나(늑대 수·날씨 세기·
  얼기 막음) 거부한다(팀 Social 연결·은신처 자리·계약 해시·대응 없는 칸·지역마다 다른 규칙·형식).
- 먹이 지도: 스냅숏 용량을 세계에 덮으면 셀 값이 그대로 들어가고 관측이 다시 만들어진다. 학습 묶음(하위 클래스)은 처음·교체 때 모두 그 지역 지도다.
- 관문: 짜 맞춘 판정 판으로 기각(P1)·보류(K2-B 없음)·통과·지킴 실패를 가른다. 두뇌 파일 다시 읽기는 저장소 두뇌 파일을 받고 깨뜨린 파일을 거부한다.
시드는 탐색 32080~32099 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import importlib.util
import json

import numpy as np
import pytest

from env.config import ROOT

ADAPT = ROOT / "results" / "v3" / "adapt" / "adapt.py"
SNAP = ROOT / "results" / "v3" / "adapt" / "unreal" / "eco_v3_snapshot_s20003_240s.json"
REF = ROOT / "results" / "v3" / "adapt" / "reference_snapshot.json"
R1_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
BRAIN = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains" / "v3_r4_g995_s0_20m.json"

pytestmark = [pytest.mark.filterwarnings("ignore:You have specified a mini-batch size"),
              pytest.mark.skipif(not R1_MODEL.exists(), reason="R1b s3 모델 zip 이 없다 (저장소 밖 ckpt)")]


def _module():
    spec = importlib.util.spec_from_file_location("adapt_v3", ADAPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ad():
    return _module()


@pytest.fixture(scope="module")
def snap(ad):
    return ad.load_snapshot(SNAP)


@pytest.fixture(scope="module")
def ref():
    return json.loads(REF.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base(ad, snap, ref):
    return ad.convert(snap, ref)


def test_default_snapshot_is_template(base):
    rec = base["record"]
    assert rec["changed"] == []                                   # 통합 레벨 기본값 = 거울 설정
    assert rec["N"] == 128 and rec["regions"] == ["Forest", "Barren", "Highland"]
    assert rec["anchor"] == "ckpt/v3/v3_r1_g995_s3_20m.zip"
    reg = base["regions"]
    assert [len(reg[r]["discs"]) for r in ("Forest", "Barren", "Highland")] == [24, 0, 9]
    assert all(reg[r]["cpp_rebuild_max_diff"] == 0.0 for r in reg)  # 풀 = C++ 세계 난수로 다시 만든 지도 (배치·방향)
    tr = base["train"]
    assert tr["features"]["integrated_stage"]["respawn"] is True and tr["overrides"]["train_seeds"] == [32000, 32050]
    assert tr["train"]["region_mix"]["obstacles"]["Forest"] == reg["Forest"]["discs"]
    assert tr["train"]["repertoire"]["allowed"] == ["graze", "flee", "hide"]
    assert base["world"]["features"]["integrated_stage"]["respawn"] is False


def test_mapped_changes(ad, snap, ref):
    s = copy.deepcopy(snap)
    s["settings"]["wolves_per_region"] = 6
    for r in s["regions"]:
        r["world"]["num_stalkers"], r["world"]["num_chasers"] = 3, 3
        if r["region"] == "Highland":
            r["world"]["weather"]["intensity"] = 0.5
        r["world"]["wild_satiation"]["sat_days"] = 0.25
        r["allowed"] = [1, 1, 1, 1, 0]                            # 얼기를 열었다
    out = ad.convert(s, ref)
    keys = {c["key"]: c["snapshot"] for c in out["record"]["changed"]}
    assert keys["overrides.rand.predator_count"] == [6, 6]
    assert keys["features.wild_satiation.sat_days"] == 0.25
    assert keys["features.wild_weather.regions"]["Highland"] == ["snow", 0.5]
    assert out["world"]["train"]["repertoire"]["allowed"] == ["graze", "flee", "hide", "freeze"]


@pytest.mark.parametrize("edit,needle", [
    (lambda s: s["settings"].__setitem__("social_control", True), "Social"),
    (lambda s: s["regions"][0]["covers"][0].__setitem__(0, 44.0), "은신처 원"),
    (lambda s: s.__setitem__("contract_hash", "0x0000000000000001"), "계약 해시"),
    (lambda s: s["settings"].__setitem__("extra_cover_count", 6), "기준 게임 값"),
    (lambda s: s["regions"][1]["world"].__setitem__("pred_eat_cd", 5), "다르다"),
    (lambda s: s["brain"].__setitem__("weights_sha256", "00" * 32), "모델 zip"),
    (lambda s: [r["world"].__setitem__("num_ranged", 1) for r in s["regions"]], "늑대 구성"),
])
def test_refusals(ad, snap, ref, edit, needle):
    s = copy.deepcopy(snap)
    edit(s)
    with pytest.raises(ad.Refused) as e:
        ad.convert(s, ref)
    assert needle in str(e.value)


def test_format_refused(ad, tmp_path, snap):
    s = dict(snap, version=2)
    p = tmp_path / "s.json"
    p.write_text(json.dumps(s), encoding="utf-8")
    with pytest.raises(ad.Refused):
        ad.load_snapshot(p)


def _cfg(ad, base, region, tmp_path):
    import yaml

    from env.config import Config
    from env_v2.config import load_v2_config

    p = tmp_path / "w.yaml"
    p.write_text(yaml.safe_dump(base["world"], allow_unicode=True, sort_keys=False), encoding="utf-8")
    c = copy.deepcopy(load_v2_config(p).to_dict())
    c["v2"]["features"]["wild_weather"]["region"] = region
    c["v2"]["features"]["obstacles"]["fixed"] = base["regions"][region]["discs"]
    return Config(c)


def test_apply_snapshot_food(ad, base, tmp_path):
    from env_v2.world import World

    w = World(_cfg(ad, base, "Barren", tmp_path), seeds=[32080])
    cap = np.asarray(base["regions"]["Barren"]["cap"])
    before = w.observe().copy()
    ad.apply_snapshot_food(w, cap)
    assert np.array_equal(w.food_cap.ravel(), cap) and np.array_equal(w.food, w.food_cap)
    assert not np.array_equal(w.observe(), before)                # 먹이 관측이 새 지도로 바뀐다
    food = np.asarray(base["regions"]["Barren"]["food"])
    ad.apply_snapshot_food(w, cap, food)
    assert np.array_equal(w.food.ravel(), food)
    with pytest.raises(ValueError):
        ad.apply_snapshot_food(w, cap[:-1])


def test_train_vec_env_uses_snapshot_food(ad, base, tmp_path):
    import yaml

    from env_v2.config import load_v2_config
    from env_v2.vec_env import MultiWorldVecEnv

    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(base["train"], allow_unicode=True, sort_keys=False), encoding="utf-8")
    cfg = load_v2_config(p)
    food = {n: r["cap"] for n, r in base["regions"].items()}
    V = ad.snapshot_food_vec_env(MultiWorldVecEnv, food)
    v = V(cfg, num_worlds=3, reset_interval=4, seeds=range(32080, 32090), meta_seed=7)
    for k, w in enumerate(v.worlds):
        assert np.array_equal(w.food_cap.ravel(), np.asarray(food[v.region_history[k][-1]]))
    v.reset()
    for _ in range(6):                                           # 교체(4 스텝)를 지나도 그 지역 지도
        v.step(np.zeros(v.num_envs, dtype=np.int64))
    assert v.num_resets >= 3
    for k, w in enumerate(v.worlds):
        r = v.region_history[k][-1]
        assert len(v.region_history[k]) >= 2
        assert np.allclose(w.food_cap.ravel(), np.asarray(food[r]))


def _fake_run(n=100, caught=None, starved=None, shelter=0.06, beh=(0.88, 0.08, 0.04, 0, 0), cover=0, regions=("A", "B")):
    rng = np.random.default_rng(32080)
    W = []
    for s in range(33000, 33000 + n):
        for r in regions:
            c = int(caught(s, r)) if caught else int(rng.integers(25, 30))
            st = int(starved(s, r)) if starved else 10
            live = 100000
            W.append(dict(seed=s, region=r, n=128, caught=c, starved=st, alive=128 - c - st, shelter_steps=int(shelter * live), live_steps=live,
                          beh_steps=[int(b * live) for b in beh], catch_cover=cover, hunt=dict(ends=10, success=6)))
    return dict(meta={}, worlds=W)


def test_gate_logic(ad):
    rng = np.random.default_rng(32081)
    base_c = {(s, r): int(rng.integers(25, 30)) for s in range(33000, 33100) for r in ("A", "B")}
    cur = _fake_run(caught=lambda s, r: base_c[(s, r)])
    same = _fake_run(caught=lambda s, r: base_c[(s, r)])
    stuck0 = dict(summary=dict(deer_stuck=0, wolf_stuck=1, wolf_wall_stuck=3, worlds=20))
    g = ad.gate_eval(cur, same, stuck0, stuck0, None)
    assert g["verdict"] == "기각" and "P1" in g["why"]           # 같은 두뇌 = 덜 잡히지 않음
    better = _fake_run(caught=lambda s, r: base_c[(s, r)] - (1 if (s + (r == "A")) % 2 else 0))
    g = ad.gate_eval(cur, better, stuck0, stuck0, None)
    assert g["criteria"]["P1_caught"]["ok"] and g["verdict"] == "보류" and "K2-B" in g["why"]
    g = ad.gate_eval(cur, better, stuck0, stuck0, cur)
    assert g["verdict"] == "통과" and g["passed"]
    g = ad.gate_eval(cur, better, stuck0, stuck0, better)
    assert g["verdict"] == "기각" and "P1b" in g["why"]
    starving = _fake_run(caught=lambda s, r: base_c[(s, r)] - (1 if (s + (r == "A")) % 2 else 0), starved=lambda s, r: 14)
    g = ad.gate_eval(cur, starving, stuck0, stuck0, cur)
    assert g["verdict"] == "기각" and "G1_starved" in g["why"]
    hiding = _fake_run(caught=lambda s, r: base_c[(s, r)] - (1 if (s + (r == "A")) % 2 else 0), shelter=0.2)
    assert "G6_no_exploit" in ad.gate_eval(cur, hiding, stuck0, stuck0, cur)["why"]
    stuck_bad = dict(summary=dict(deer_stuck=2, wolf_stuck=1, wolf_wall_stuck=3, worlds=20))
    assert "G5_stuck" in ad.gate_eval(cur, better, stuck0, stuck_bad, cur)["why"]
    g = ad.gate_eval(cur, better, None, None, cur)
    assert g["verdict"] == "보류"


@pytest.mark.skipif(not BRAIN.exists(), reason="저장소 두뇌 파일이 없다")
def test_verify_brain_file(ad, tmp_path):
    v = ad.verify_brain_file(BRAIN)
    assert v["ok"] and v["sha256_ok"] and v["actions_ok"] and v["max_logit_err"] <= v["tolerance"]
    d = json.loads(BRAIN.read_text(encoding="utf-8"))
    d["golden"]["cases"][0]["logits"][0] += 0.01                  # 골든을 틀리게
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    assert not ad.verify_brain_file(p)["ok"]


def test_gate_constants_match_md(ad):
    md = (ROOT / "results" / "v3" / "adapt" / "GATE.md").read_text(encoding="utf-8")
    g = ad.GATE
    for txt in ("33000~33099", "32060~32079", "32050~32069", "33000~33009", "32080~32099", "−1.984", "+2.626", "3 마리", "2배", "3M"):
        assert txt in md
    assert g["judge_seeds"] == (33000, 33099) and g["select_seeds"] == (32060, 32079) and g["check_seeds"] == (32050, 32069)
    assert g["t_crit"] == 1.984 and g["t_region"] == 2.626 and g["check_abs"] == 3.0 and ad.DEFAULT_STEPS == 3_000_000
