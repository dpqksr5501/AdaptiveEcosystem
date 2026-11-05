"""판 5 두뇌(R7e — 관측 24 두 길 + 반사 밖 두뇌 FLEE 막음, 계약 0xad7bad5e1acaf071)용 실시간 고리 예비 측정 (10-27, LIVE_GATE.md 7절·변경 기록 (8)·(9)).
사용자 10-27 '실제 폴더 잠금 풀자' — 관문 크기(N·G 판 길이, 판정 시드 수, 학습 스텝·K, 최소 차이 δ_H, 중간 판정)를 고르는 자료다. 판정이 아니다.
예비 시드 34900~34999 만 쓴다(관문 시드 35000~35199 는 쓰지 않는다). 실제 폴더 Saved/EcoAdapt 는 쓰지 않는다(시험 폴더 --root).

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/live/pilot_mask5/pilot_mask5.py make --base-j <J 바탕>     # 1) 환경 변화 스냅숏 8 개 + 대조 1 (snapshots/ — 아래 VARIANTS)
    python results/v3/live/pilot_mask5/pilot_mask5.py run --variant I_t20 --root <시험 폴더> [--steps 1000000 2000000 4000000] [--extra-same]
                                                                                 # 2) 변형 하나 = live.py pilot 한 번 (같은 코드 — live.main 을 그대로 부르고
                                                                                 #    판정 세계 결과를 버리지 않고 raw/<변형>.json.gz 로 남긴다)
    python results/v3/live/pilot_mask5/pilot_mask5.py analyze --raw <raw 폴더>   # 3) 표·json (pilot.md, summary.json, seeds/<변형>.json.gz)
    python results/v3/live/pilot_mask5/pilot_mask5.py timing --variant I_t20 --root <시험 폴더> [--steps 1000000]   # 4) 한 바퀴 시간 (timing/)

환경 변화 (사용자 10-27 '두뇌를 다시 배우는 건 큰 변화만' — 날씨 종류 바뀜·나무 일정 수 이상 변함. 다음 단계 '숲이 점점 자람' 모드와 같은 꼴):
  - 바탕 스냅숏 둘 (둘 다 게임이 R7e 두뇌를 건 Play 의 실제 스냅숏):
    I = 통합 맵 /Game/Map/LV_Ecosystem_IntegrationTest 세션 20004 63.1 초 (10-24 route5_test — 시험용 대역이 Barren 나무 0→20·맑음→비를 한 뒤의 스냅숏).
        바뀌기 전 Barren(나무 0·맑음)으로 되돌린 뒤 변화를 얹는다.
    J = 조연우 맵 복사본 /Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem 세션 20010 240 초 대조 모드 (10-25 level_jyu_eco — 팀 life·식생·이주·팀 비 끔, 나무 0).
  - 나무 +10·+20·+30 (Barren): 게임 시험용 대역 eco.IntegratedV3.Test.AddTrees 와 같은 규칙(EcoV3EnvWatch.cpp TestAddTrees — 줄기 반지름
    40.45 cm × 크기 U[1.8, 2.2] ÷ 200, 벽 4 m·은신처 둘레 2 m·줄기 사이 3 m 띄움, 무대 안 고른 자리)으로 파이썬 난수(TREE_SEED)로 30 그루를 차례로 놓고
    앞 10·20·30 그루를 쓴다 — 숲이 자라는 차례처럼 겹친다(+10 ⊂ +20 ⊂ +30). C++ 난수와 자리는 다르다(규칙만 같다). 원판은 게임처럼 (x, y, r) 순.
  - 날씨 종류 바뀜: I = Barren 맑음 → 비 1.00 (시험용 대역 cvar eco.IntegratedV3.WeatherBarren 과 같은 바뀜), J = Highland 눈 1.00 → 비 0.65 (팀 날씨가 그 맵에서
    실제로 만든 바뀜 — 10-25 live_a 스냅숏 #19 의 값 그대로).
  - 10-27 게임 기본(eco.IntegratedV3.GrazeCalm·RestKeep 1 — LIVE_GATE.md 변경 기록 (9))을 얹는다: 두 바탕 스냅숏은 10-27 전 것이라 그 칸이 없어 변환기가 끈 세계로
    읽는다. 지금 게임이 쓰는 스냅숏처럼 지역 world.graze_calm·world.wild_flight.rest_keep* 를 C++ 기본 값(EcoV3Snapshot.cpp 가 쓰는 칸, 값 = configs/
    v3_wild3_route5_calm_mirror.yaml)으로 적는다 — 판정·학습 세계가 켠 세계가 된다(변경 기록 (9) '켠 세계에서 예비 측정을 다시 한다').
  - 스냅숏 env 블록에 합성 바뀜(source 'pilot_mask5')을 적는다. 그 밖 칸(먹이 지도·은신처·사슴 수·두뇌)은 바탕 그대로다.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
LIVE_DIR = HERE.parents[1]                          # results/v3/live
ROOT = HERE.parents[4]                              # herbivore_rl/
for p in (ROOT, LIVE_DIR, ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
          ROOT / "results" / "v3" / "wild2"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

PROJECT = ROOT.parent / "AdaptiveEcosystem"
SNAP_DIR = HERE.parent / "snapshots"
SEEDS_DIR = HERE.parent / "seeds"
VAR_DIR = HERE.parent / "variants"
# 바탕 스냅숏 (저장소 밖 — 만든 사본은 snapshots/ 에 남긴다. 바탕 지문은 make 가 manifest 에 적는다)
BASE_I = PROJECT / "Saved" / "EcoAdapt_route5_test" / "snapshots" / "eco_v3_snapshot_s20004_t473_e1.json"
BASE_J_DEFAULT = None                               # make --base-j 로 준다 (10-25 level_jyu_eco 의 세션 임시 폴더 control/s20010_r7e.json)
TREE_SEED = 20261027                                # 파이썬 나무 자리 난수 (규칙은 C++ TestAddTrees 와 같고 난수만 다르다)
TREE_REGION = "Barren"
# C++ 상수 (TreeLayoutV3.h · EcoV3EnvWatch.cpp · EcoRepertoire.h kUnitCm 200)
UNIT_CM = 200.0
TRUNK_R_MESH_CM, SCALE_LO, SCALE_HI = 40.45, 1.8, 2.2
COVER_CLEAR_M, WALL_CLEAR_M, GAP_M = 2.0, 4.0, 3.0
TREE_TRIES = 400
# 10-27 게임 기본 (EcoPolicyV3IntegratedSubsystem.h — RestKeep 1: margin 2.0·band 4.0, GrazeCalm 1: CalmGoldenVectorsV3.h 값 = calm mirror)
CALM_WILD_FLIGHT = dict(rest_keep=True, rest_keep_margin=2.0, rest_keep_band=4.0, rest_keep_asleep=False)
CALM_GRAZE = dict(graze_edge_r=2.0, graze_edge_w=2.5, graze_inertia=0.5, graze_wall_margin=1.0)
VARIANTS = {
    "I_t10": dict(base="I", trees=10, label="통합 맵 Barren 나무 0→10"),
    "I_t20": dict(base="I", trees=20, label="통합 맵 Barren 나무 0→20"),
    "I_t30": dict(base="I", trees=30, label="통합 맵 Barren 나무 0→30"),
    "I_wx": dict(base="I", weather=("Barren", "rain", 1.0), label="통합 맵 Barren 맑음→비 1.00"),
    "J_t10": dict(base="J", trees=10, label="조연우 맵 Barren 나무 0→10"),
    "J_t20": dict(base="J", trees=20, label="조연우 맵 Barren 나무 0→20"),
    "J_t30": dict(base="J", trees=30, label="조연우 맵 Barren 나무 0→30"),
    "J_wx": dict(base="J", weather=("Highland", "rain", 0.6499999761581421), label="조연우 맵 Highland 눈→비 0.65"),
    # 대조 (크기를 고르는 변형이 아니다): I_t20 과 같고 10-27 고침 두 칸만 끈 세계(옛 스냅숏 그대로 읽힘) — 후보가 숨음을 잃는 까닭이 켠 세계인지 가르려고
    "I_t20_off": dict(base="I", trees=20, calm=False, label="통합 맵 Barren 나무 0→20 · 10-27 고침 끈 세계 (대조)"),
}
WX_NOW = {   # weather_now (C++ 이 지역 날씨에서 셈한 값 — 스냅숏에 그대로 적힌 값을 옮김, 변환기는 world.weather 만 읽는다)
    ("rain", 1.0): dict(sight=0.9, hear=0.5, deer_speed=1, wolf_speed=1),
    ("rain", 0.6499999761581421): dict(sight=0.9350000023841858, hear=0.675000011920929, deer_speed=1, wolf_speed=1),
    ("clear", 0.0): dict(sight=1, hear=1, deer_speed=1, wolf_speed=1),
}
KO_WX = {"clear": "맑음", "rain": "비", "snow": "눈"}


def sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def grow_trees(size: float, covers, avoid, count: int, seed: int, region_index: int) -> list:
    """C++ TestAddTrees 와 같은 규칙으로 count 그루를 차례로 놓는다 (파이썬 난수). 반환 = 놓은 차례대로 [x, y, r]."""
    g = np.random.default_rng([0x56335454, int(seed), int(region_index) + 1])
    wall = WALL_CLEAR_M * 100.0 / UNIT_CM
    clear = COVER_CLEAR_M * 100.0 / UNIT_CM
    gap = GAP_M * 100.0 / UNIT_CM
    av = [list(map(float, d)) for d in avoid]
    out = []
    for _ in range(count):
        for _try in range(TREE_TRIES):
            scale = g.uniform(SCALE_LO, SCALE_HI)
            g.uniform(0.0, 360.0)                                   # 방향 (원판에 쓰지 않음 — C++ 과 같은 차례로 뽑는다)
            r = TRUNK_R_MESH_CM * scale / UNIT_CM
            x = g.uniform(wall + r, size - wall - r)
            y = g.uniform(wall + r, size - wall - r)
            ok = all(not (float(c[2]) > 0.0 and math.hypot(x - float(c[0]), y - float(c[1])) < float(c[2]) + clear + r) for c in covers)
            ok = ok and all(math.hypot(x - d[0], y - d[1]) >= d[2] + r + gap for d in av)
            if ok:
                out.append([x, y, r])
                av.append([x, y, r])
                break
        else:
            raise SystemExit(f"나무 {len(out) + 1} 번째 자리를 {TREE_TRIES} 번 안에 못 찾았다")
    return out


def set_weather(reg: dict, kind: str, intensity: float) -> None:
    reg["world"]["weather"]["kind"] = kind
    reg["world"]["weather"]["intensity"] = intensity
    reg["weather_now"] = dict(kind=kind, intensity=intensity, **WX_NOW[(kind, intensity)])


def add_calm(snap: dict) -> None:
    snap["settings"]["rest_keep"] = True
    snap["settings"]["graze_calm"] = True
    for r in snap["regions"]:
        r["world"]["wild_flight"].update(CALM_WILD_FLIGHT)
        r["world"]["graze_calm"] = dict(CALM_GRAZE)


def set_discs(reg: dict, discs: list) -> None:
    d = sorted([list(map(float, t)) for t in discs])                # 게임과 같은 (x, y, r) 순
    o = reg["obstacles"]
    o["discs"] = d
    o["scan_discs"] = copy.deepcopy(d)
    o["foliage_trees"] = [1] * len(d)
    o["level_trees"] = len(d)
    o["level_trunks"] = len(d)
    o["level_trees_unmatched"] = len(d)                              # 시험용 나무는 배치 표 밖 (e1 의 Barren 20 그루와 같은 꼴)
    o["level_trees_snapped"] = 0


def cmd_make(a) -> int:
    base_j = Path(a.base_j)
    bases = {"I": Path(a.base_i), "J": base_j}
    raw = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in bases.items()}
    # 바뀌기 전 바탕: I 는 Barren 시험용 나무 20 그루·비를 빼고 맑음으로(스냅숏 env 의 바뀜 #1 을 되돌림), J 는 그대로(환경 판 0)
    pre = {}
    for k, s in raw.items():
        s = copy.deepcopy(s)
        if k == "I":
            reg = next(r for r in s["regions"] if r["region"] == TREE_REGION)
            assert s["env"]["revision"] == 1 and len(reg["obstacles"]["discs"]) == 20, "I 바탕은 Barren 나무 0→20·맑음→비 #1 스냅숏이어야 한다"
            set_discs(reg, [])
            set_weather(reg, "clear", 0.0)
        pre[k] = s
    trees = {}
    for k, s in pre.items():
        reg = next(r for r in s["regions"] if r["region"] == TREE_REGION)
        trees[k] = grow_trees(float(reg["size"]), reg["covers"], reg["obstacles"]["discs"], 30, TREE_SEED, int(reg["region_index"]))
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    man = dict(made_by="pilot_mask5.py make", tree_seed=TREE_SEED, tree_region=TREE_REGION,
               bases={k: dict(file=p.name, sha256=sha256(p), map=raw[k].get("map"), session_seed=raw[k]["session_seed"],
                              global_step=raw[k]["global_step"], sim_seconds=raw[k]["sim_seconds"], brain=raw[k]["brain"]["id"],
                              env_revision=raw[k]["env"]["revision"]) for k, p in bases.items()},
               trees30={k: [[round(v, 6) for v in t] for t in tt] for k, tt in trees.items()},
               calm=dict(wild_flight=CALM_WILD_FLIGHT, graze_calm=CALM_GRAZE), variants={})
    for name, v in VARIANTS.items():
        s = copy.deepcopy(pre[v["base"]])
        if v.get("calm", True):
            add_calm(s)
        changes = []
        step = int(s["global_step"])
        if v.get("trees"):
            reg = next(r for r in s["regions"] if r["region"] == TREE_REGION)
            set_discs(reg, trees[v["base"]][: v["trees"]])
            changes.append(dict(revision=1, step=step, seconds=s["sim_seconds"], region=TREE_REGION, kind="trees",
                                detail=f"나무 0→{v['trees']} (+{v['trees']} −0)", source="pilot_mask5"))
        if v.get("weather"):
            rname, kind, inten = v["weather"]
            reg = next(r for r in s["regions"] if r["region"] == rname)
            w0 = reg["world"]["weather"]
            before = f"{KO_WX[w0['kind']]} {float(w0['intensity']):.2f}"
            set_weather(reg, kind, inten)
            changes.append(dict(revision=1, step=step, seconds=s["sim_seconds"], region=rname, kind="weather",
                                detail=f"{before}→{KO_WX[kind]} {inten:.2f}", source="pilot_mask5"))
        s["env"] = dict(watch=True, revision=1, changed_step=step, first_changed_step=step, trigger="env_change", changes=changes)
        s["why"] = (f"예비 측정 합성 (pilot_mask5 {name} — {v['label']}, "
                    + ("10-27 게임 기본 GrazeCalm·RestKeep 켬)" if v.get("calm", True) else "10-27 고침 칸 없음 = 끈 세계)"))
        out = SNAP_DIR / f"{name}.json"
        out.write_text(json.dumps(s, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        man["variants"][name] = dict(v, file=out.name, sha256=sha256(out), changes=changes)
        print(f"{name}: {v['label']} -> {out.name}")
    (SNAP_DIR / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


# --------------------------------------------------------------------- #
# run — live.py pilot 한 번 (live.main 그대로) + 판정 세계 결과 남기기
# --------------------------------------------------------------------- #


def cmd_run(a) -> int:
    import live

    captured: list = []
    orig = live.gather

    def gather(results, models, steps):                              # live.gather 그대로 + 결과를 버리지 않고 남긴다 (판정 셈은 바꾸지 않는다)
        out = orig(results, models, steps)
        captured.append(dict(models={k: live.path_text(v) for k, v in models.items()}, res=out))
        return out

    live.gather = gather
    snap = SNAP_DIR / f"{a.variant}.json"
    argv = ["pilot", "--snapshot", str(snap), "--root", str(a.root), "--seeds", a.seeds, "--cand-seeds", a.cand_seeds,
            "--horizons", *[str(h) for h in a.horizons], "--steps", *[str(s) for s in a.steps], "--model-seeds", *[str(s) for s in a.model_seeds],
            "--parts", *a.parts]
    if a.workers:
        argv += ["--workers", str(a.workers)]
    if a.flight_cost:
        argv += ["--flight-cost", *[str(x) for x in a.flight_cost]]
    if a.extra_same:
        argv += ["--extra-models", "same=ckpt/v3/v3_r7_g995_s1_20m.zip"]
    t0 = time.perf_counter()
    rc = live.main(argv)
    wall = time.perf_counter() - t0
    pdirs = sorted((Path(a.root) / "live" / "pilot").glob("p_*"), key=lambda p: p.stat().st_mtime)
    pd = pdirs[-1]
    raw_dir = Path(a.raw)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rawp = raw_dir / f"{a.variant}{a.tag}.json.gz"
    with gzip.open(rawp, "wt", encoding="utf-8") as f:
        json.dump(dict(variant=a.variant, tag=a.tag, pilot=pd.name, argv=argv, wall_s=round(wall, 1), captured=captured), f)
    vd = VAR_DIR / f"{a.variant}{a.tag}"
    vd.mkdir(parents=True, exist_ok=True)
    for name in ("pilot.json", "pilot.md"):
        (vd / name).write_text((pd / name).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    shown = {str(a.root): "<시험 폴더>", str(snap): snap.relative_to(ROOT).as_posix()}
    (vd / "command.txt").write_text(
        "# herbivore_rl/ 에서 (PYTHONUTF8=1) — pilot_mask5.py run 이 live.main 에 그대로 넘긴 인수 (판정 세계 결과를 raw 로 남기는 것만 더함)\n"
        f"python results/v3/live/pilot_mask5/pilot_mask5.py run --variant {a.variant}{f' --tag {a.tag}' if a.tag else ''} --root <시험 폴더> --raw <raw 폴더>"
        f"{' --extra-same' if a.extra_same else ''} …\n"
        "python results/v3/live/live.py " + " ".join(shown.get(x, x) for x in argv)
        + f"\n# 벽시계 {wall:.0f} 초, 예비 측정 폴더 {pd.name}\n", encoding="utf-8", newline="\n")
    cv = json.loads((pd / "convert.json").read_text(encoding="utf-8"))
    (vd / "convert.json").write_text(json.dumps(cv, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {vd} (raw {rawp}, {wall:.0f} 초)")
    return rc


def cmd_timing(a) -> int:
    """한 바퀴 시간 재기 (판 흉내 — 예비 시드로, 관문 판정 없음): run_round 와 같은 차례·워커 수로
    변환 → 학습 S (모델 1) ‖ 지금 두뇌 N(시드 n × H_N)·G(n_G × H_G)·끼임(5 × H_G, 파이썬) [워커 W − 1] → 후보 N 앞 절반 [W] → 뒤 절반·G·끼임 [W] → 두뇌 파일 쓰기·
    다시 읽기(A5, 시험 폴더). 끼임만 따로 한 번 더 잰다(파이썬 몫 나누기)."""
    import live

    snap = SNAP_DIR / f"{a.variant}.json"
    s = live.read_snapshot(snap)
    rid = f"tm_{a.variant}_{time.strftime('%m%dT%H%M%S')}"                # 짧게 (학습 체크포인트 경로가 윈도 260 자를 넘지 않게)
    rd = Path(a.root) / "timing" / rid
    W = int(a.workers)
    t: dict = dict(variant=a.variant, n=a.n, horizon=a.horizon, n_g=a.n_g, horizon_g=a.horizon_g, steps=a.steps, workers=W)
    t0 = time.perf_counter()
    info = live.prepare(snap, s, rd, live.brain_folders(Path(a.root)))
    t["convert"] = round(time.perf_counter() - t0, 1)
    start = Path(live.ad.ROOT / info["record"]["anchor"])
    lo = 34900
    judge = list(range(lo, lo + a.n))
    judge_g = list(range(lo, lo + a.n_g))
    stuck = list(range(lo, lo + 5))
    t0 = time.perf_counter()
    procs = live.launch_training(info, rd, start, rid, [0], a.steps, a.steps, live.CKPT)       # 실제 고리와 같은 후보 폴더 (ckpt/v3/live — git 밖)
    items = (live.eval_items(info, "current", start, judge, a.horizon, "N") + live.eval_items(info, "current", start, judge_g, a.horizon_g, "G")
             + live.stuck_items(info, "current", start, stuck, a.horizon_g))
    t1 = time.perf_counter()
    live.eval_runner(items, max(1, W - 1))
    t["eval_current"] = round(time.perf_counter() - t1, 1)
    rows = live.wait_training(procs)
    t["train_and_eval_current"] = round(time.perf_counter() - t0, 1)
    t["train_learn"] = rows[0].get("learn_s")
    t["train_steps_per_sec"] = rows[0].get("steps_per_sec")
    cand = Path(rows[0]["model"])
    k = live.seq_sizes(a.n) or a.n
    t1 = time.perf_counter()
    live.eval_runner(live.eval_items(info, "candidate", cand, judge[:k], a.horizon, "N"), W)
    t["eval_candidate_N1"] = round(time.perf_counter() - t1, 1)
    t1 = time.perf_counter()
    live.eval_runner(live.eval_items(info, "candidate", cand, judge[k:], a.horizon, "N") + live.eval_items(info, "candidate", cand, judge_g, a.horizon_g, "G")
                     + live.stuck_items(info, "candidate", cand, stuck, a.horizon_g), W)
    t["eval_candidate_N2_G_stuck"] = round(time.perf_counter() - t1, 1)
    t1 = time.perf_counter()
    e = live.env_info(s)
    live.export_brain(cand, rd / "brains", 1, 1, rid, snap.name, live.env_summary(s), "예비 측정 시간 재기 (관문 아님)", str(s.get("play_id", "")))
    t["export"] = round(time.perf_counter() - t1, 1)
    t1 = time.perf_counter()
    live.eval_runner(live.stuck_items(info, "current", start, stuck, a.horizon_g), W)
    t["stuck_only"] = round(time.perf_counter() - t1, 1)
    t["round_futility_s"] = round(t["convert"] + t["train_and_eval_current"] + t["eval_candidate_N1"] + 1.0, 1)
    t["round_full_s"] = round(t["convert"] + t["train_and_eval_current"] + t["eval_candidate_N1"] + t["eval_candidate_N2_G_stuck"] + t["export"] + 1.0, 1)
    t["env"] = e.get("revision")
    out = HERE.parent / "timing"
    out.mkdir(exist_ok=True)
    p = out / f"timing_{a.variant}_n{a.n}_h{a.horizon}_g{a.n_g}x{a.horizon_g}_s{a.steps // 1_000_000}m.json"
    p.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(t, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("make")
    s.add_argument("--base-i", default=str(BASE_I))
    s.add_argument("--base-j", required=True)
    s = sub.add_parser("run")
    s.add_argument("--variant", required=True, choices=list(VARIANTS))
    s.add_argument("--tag", default="")
    s.add_argument("--root", required=True)
    s.add_argument("--raw", required=True)
    s.add_argument("--workers", type=int, default=None)
    s.add_argument("--seeds", default="34900-34999")
    s.add_argument("--cand-seeds", default="34900-34999")
    s.add_argument("--horizons", type=int, nargs="+", default=[900, 1800, 2700, 3600])
    s.add_argument("--steps", type=int, nargs="+", default=[1_000_000, 2_000_000])
    s.add_argument("--model-seeds", type=int, nargs="+", default=[0, 1])
    s.add_argument("--flight-cost", type=float, nargs="+", default=None)
    s.add_argument("--parts", nargs="+", default=["brains", "cands"])
    s.add_argument("--extra-same", action="store_true", help="같은 두뇌(R7e zip)를 '더 견줄 두뇌'로 한 번 더 — 판정이 결정적인지(차이 0)")
    s = sub.add_parser("analyze")
    s.add_argument("--raw", required=True)
    s = sub.add_parser("timing")
    s.add_argument("--variant", required=True, choices=list(VARIANTS))
    s.add_argument("--root", required=True)
    s.add_argument("--workers", type=int, default=14)
    s.add_argument("--n", type=int, default=80)
    s.add_argument("--horizon", type=int, default=1800)
    s.add_argument("--n-g", type=int, default=40)
    s.add_argument("--horizon-g", type=int, default=3600)
    s.add_argument("--steps", type=int, default=2_000_000)
    a = ap.parse_args(argv)
    if a.cmd == "analyze":
        import pilot_mask5_analyze as an

        return an.main(a)
    return {"make": cmd_make, "run": cmd_run, "timing": cmd_timing}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
