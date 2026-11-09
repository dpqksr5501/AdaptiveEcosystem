"""v3 R7 (반사 밖 두뇌 FLEE 막음 — 마스크 판 5) 점검·고르기·판정 도구 — 사전 등록 results/v3/r7/PREREG.md 4~7절.

R6 도구(results/v3/r6/r6_eval.py — 판정 세계·실행기·탐침·길 지킴·셈 함수)를 불러 쓰고 R7 에서 바뀐 곳만 여기 둔다(R6 도구는 고치지 않는다):
  - 시드: R7 칸 38000~38199 (판정 N 38000~38099 · G 38000~38039 · 끼임 38000~38004 · 고르기 38100~38119 · 점검 38120~38139).
  - 두뇌 → 세계 키: 두뇌(zip)의 마스크 판으로 정한다 — 관측 칸 수로는 판 4·5 를 가를 수 없다(둘 다 관측 24):
      판 4 (route0·R6 두뇌)            wild_flight.route 켬
      판 5 (R7·시작 두뇌 route0m5)      wild_flight.route 켬 + wild_flight.brain_flee_outside_reflex false
      판 6 (대조 '길 끔')               wild_flight.brain_flee_outside_reflex false (관측 21)
      판 2 (obs21zero)                 키 없음 — 'shelter_rule' = obs21zero + wild_flight.route_fixed shelter(측정용 '늘 SHELTER' 손 규칙, 보고만)
  - 세계마다 막음 통계 gate(World.flee_gate_stats — 판 5·6 세계만: 덮기 밖 결정 수·그 가운데 두뇌 FLEE 수)를 적는다. 정책 껍질에서 세계를 읽기만 한다
    (세계·궤적 그대로). 조기 점검 결함 = 반사 밖 두뇌 FLEE > 0(마스크가 막으므로 늘 0 이어야 한다).
  - 본 학습 2M·5M 점검 (c) 에 GF(1000 산 사슴-스텝당 시작한 도망)·GR(살아 끝난 도망 뒤 5 초 안 다시 도망) route0 대비 짝 t < +2.0 을 더한다(R6 교훈 —
    R6 는 이 둘이 판정에서 걸렸다). 모델 고르기도 GF·GR 짝 t < +2.0 인 모델 가운데서만 고른다.
  - 판정 보고 줄: 대조 '길 끔'·'늘 SHELTER'·R6 고른 두뇌(v3_r6_g995_s1_20m)와의 차이(GF·GR 포함), 막음 통계, 두뇌 스스로 뛴 도망(길 none) 수.
  - A5 계약 = 관측 24 · 마스크 판 5 · 0xad7bad5e1acaf071 (골든 세계 configs/v3_wild3_route5_mirror.yaml — export_weights_v3 가 판으로 고른다).
판정 실행기는 R6 와 같은 파이썬 거울(live._world_multi → run_mirror.run_world)이다(판 5 는 C++ 평가기에 없다 — ceval 이 거부한다).

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/r7/r7_eval.py run --use check --model route0 --probe --name early_base         # 점검 기준 판 (38120~38139)
    python results/v3/r7/r7_eval.py run --use check --model ckpt/v3/<점검 체크포인트>.zip --probe --name early_<꼬리>
    python results/v3/r7/r7_eval.py check --run results/v3/r7/runs/early_<꼬리>.json --base results/v3/r7/runs/early_base.json
    python results/v3/r7/r7_eval.py select --models ckpt/v3/v3_r7_g995_s0_20m.zip ckpt/v3/v3_r7_g995_s1_20m.zip ckpt/v3/v3_r7_g995_s2_20m.zip
    python results/v3/r7/r7_eval.py judge --model ckpt/v3/v3_r7_g995_s<고른 시드>_20m.zip --off ckpt/v3/v3_r7off_g995_s0_20m.zip
    python results/v3/r7/r7_eval.py run --use smoke --model route0m5 --probe --seeds 32080-32081 --steps 300 --name smoke_route0m5 --out-dir <임시>

쓰임(--use)이 시드·길이·세계를 정한다(사전 등록 2절 — 다른 쓰임의 시드를 쓸 수 없다):
  check   본 학습 점검 38120~38139 × 지역 셋, N, 1800 스텝
  select  모델 고르기 38100~38119 × 지역 셋, N, 1800 스텝
  judge_n 판정 N      38000~38099 × 지역 셋, N, 1800 스텝 (P1·GH·GN·GF·GV·GC·GT·GTr·GR·G4 N, 보고 줄)
  judge_g 판정 G      38000~38039 × 지역 셋, G, 3600 스텝 (GG·G4 G·G6)
  stuck   끼임 G5     38000~38004 × 지역 셋, G, 3600 스텝
  smoke   도구 확인   32080~32099 안(--seeds·--steps 를 준다), N — R7 시드 38000~38199 · R6 시드 37000~37199 는 받지 않는다
--probe(점검): R6 탐침(r6_eval._Probe) 그대로 — 길 결정의 SHELTER 확률과 도주 스텝의 가치망 설명 분산을 함께 잰다(세계·궤적 그대로).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import pickle
import re
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
R6_DIR = ROOT / "results" / "v3" / "r6"
for _p in (ROOT, R6_DIR, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import r6_eval as R6  # noqa: E402  ← env.torch_init·경로(adapt·mirror·r4·wild2·live)를 먼저 준비한다

lv, re_, ad = R6.lv, R6.re_, R6.ad

OUT = HERE.parent / "runs"                          # git 밖 (herbivore_rl/.gitignore runs/)
CK = ROOT / "ckpt" / "v3"
ROUTE0 = R6.ROUTE0                                  # 판정·점검·고르기의 기준 = 지금 두뇌 route0 (관측 24·판 4 — 배포 결정 = R1b-F, 길은 늘 RUN)
ROUTE0M5 = CK / "v3_r1_g995_s3_obs24route0m5.zip"   # R7 시작 두뇌 (route0 가중치 그대로 + 판 5 — results/v3/r7/r7_start.py)
OBS21ZERO = R6.OBS21ZERO                            # 판 2 ('늘 SHELTER' 규칙의 도주 밖 두뇌)
OBS21M6 = CK / "v3_r1_g995_s3_obs21zero_m6.zip"     # R7 대조 '길 끔' 시작 두뇌 (판 6)
R6_PICK = CK / "v3_r6_g995_s1_20m.zip"              # R6 고른 두뇌 (판 4 — 보고 줄 'R7 − R6')
BRAINS = HERE.parent / "brains"
CONTRACT_R7 = "0xad7bad5e1acaf071"                  # 관측 24·마스크 판 5 계약 해시 (설계 17-3)
GATE_KEY = "wild_flight.brain_flee_outside_reflex"
GAMMA = R6.GAMMA                                    # 0.995
LAM = 0.98                                          # 학습 GAE λ (R6 조기 점검이 고른 값으로 고정 — (b) 의 수익 목표)
FLIGHT_COST = 0.0                                   # 도주 비용 (R6 조기 점검이 고른 값으로 고정 — 학습 세계 flight_cost 0.0)
STEP_S = lv.STEP_S
REGIONS = R6.REGIONS

# 쓰임 → (시드 처음, 끝, 길이, 세계) — 사전 등록 2절
USES = {
    "judge_n": (38000, 38099, 1800, "N"),
    "judge_g": (38000, 38039, 3600, "G"),
    "stuck": (38000, 38004, 3600, "stuck"),
    "select": (38100, 38119, 1800, "N"),
    "check": (38120, 38139, 1800, "N"),
}
R7_SEEDS = (38000, 38199)                           # R7 사전 등록 시드 칸 — 쓰임 밖에서는 받지 않는다
SMOKE_SEEDS = (32080, 32099)                        # 도구 확인 (탐색 칸 32000~32099 의 스모크 몫 — R6 와 같다)

# 마스크 판 → 두뇌가 쓰는 세계 키 (사전 등록 1-3)
WORLD_SETS = {4: {"wild_flight.route": True}, 5: {"wild_flight.route": True, GATE_KEY: False}, 6: {GATE_KEY: False}, 2: {}}
OBS_OF_MASK = {4: 24, 5: 24, 6: 21, 2: 21}

# 본 학습 점검 규칙 (사전 등록 5절 — R6 5-1 그대로 + (c) 에 GF·GR, 결함에 반사 밖 두뇌 FLEE)
EARLY = dict(
    pi_move=0.05,          # (a) SHELTER 가 열린 길 결정에서 학습 표본 확률 π′(SHELTER) 평균이 route0 값에서 이보다 크게 움직임 (|차이| > 0.05)
    ev_min=0.0,            # (b) 도주 스텝(도주 반사 덮기 중인 산 사슴) 가치망 설명 분산(λ 0.98 λ-수익 목표) > 0
    t_hide=-2.0,           # (c) 숨음 비율 짝 t > −2
    t_caught_ratio=2.0,    # (c) 잡힘 비율(쫓긴 도망 가운데) 짝 t < +2
    t_caught=2.0,          # (c) 잡힌 몫(사슴 가운데) 짝 t < +2
    t_gf=2.0,              # (c) GF 1000 산 사슴-스텝당 시작한 도망 짝 t < +2   (R7 새 칸 — R6 교훈)
    t_gr=2.0,              # (c) GR 살아 끝난 도망 뒤 5 초 안 다시 도망 수 짝 t < +2 (R7 새 칸 — 길 기록이 없는 대조 '길 끔'은 세지 않는다)
)
# 모델 고르기 자격 (사전 등록 6절 — 고르기 시드에서 route0 대비 짝 t)
SELECT = dict(t_gf=2.0, t_gr=2.0)


# --------------------------------------------------------------------- #
# 두뇌·세계
# --------------------------------------------------------------------- #

def model_mask_version(path: Path) -> int:
    """모델 zip 의 마스크 판(policy_kwargs rep_mask_version — SB3 가 data 에 피클로 적는다. 우리 학습·r7_start 가 만든 파일만 읽는다)."""
    d = json.loads(zipfile.ZipFile(path).read("data"))
    pk = d.get("policy_kwargs") or {}
    if isinstance(pk, dict) and ":serialized:" in pk:
        pk = pickle.loads(base64.b64decode(pk[":serialized:"]))     # noqa: S301 — 저장소가 만든 모델 파일
    v = pk.get("rep_mask_version") if isinstance(pk, dict) else None
    if v is None:
        raise ValueError(f"{path}: 마스크 판(rep_mask_version)이 없다 — 행동 고르기(v3) 모델이 아니다")
    return int(v)


NAMED = {"route0": ROUTE0, "route0m5": ROUTE0M5, "obs21zero": OBS21ZERO, "obs21zero_m6": OBS21M6, "r6": R6_PICK}


def resolve_model(text: str) -> dict:
    """'route0' · 'route0m5' · 'obs21zero' · 'obs21zero_m6' · 'r6' · 'shelter_rule' · 모델 zip 경로 → dict(label, path, obs, mask, sets — 두뇌가 쓰는 세계 키).
    세계 키는 두뇌의 마스크 판으로 정한다(WORLD_SETS). 관측 칸 수와 판이 맞지 않거나 모르는 판이면 멈춘다."""
    if text == "shelter_rule":
        return dict(label="shelter_rule", path=OBS21ZERO, obs=21, mask=2, sets={"wild_flight.route_fixed": "shelter"})
    p = NAMED.get(text)
    if p is None:
        p = Path(text)
        p = p if p.is_absolute() else ROOT / p
    if not p.exists():
        raise SystemExit(f"모델 {p} 이 없다")
    obs, mv = R6.model_obs_dim(p), model_mask_version(p)
    if mv not in WORLD_SETS or OBS_OF_MASK[mv] != obs:
        raise SystemExit(f"{p}: 관측 {obs} 칸 · 마스크 판 {mv} 두뇌는 받지 않는다 (R7 = 관측 24·판 5, route0·R6 = 24·4, 대조 = 21·6, obs21zero = 21·2)")
    return dict(label=text if text in NAMED else p.stem, path=p, obs=obs, mask=mv, sets=dict(WORLD_SETS[mv]))


def use_plan(use: str, seeds=None, steps=None) -> dict:
    """쓰임 → dict(use, seeds, steps, world). smoke 만 --seeds·--steps 를 받고(SMOKE_SEEDS 안), 그 밖의 쓰임은 사전 등록 값만 쓴다."""
    if use == "smoke":
        if not seeds or not steps:
            raise SystemExit("--use smoke 는 --seeds 와 --steps 를 준다")
        lo, hi = SMOKE_SEEDS
        bad = [s for s in seeds if not lo <= int(s) <= hi]
        if bad:
            raise SystemExit(f"스모크 시드 {bad[:5]} 는 {lo}~{hi} 밖이다 (R7 사전 등록 시드 {R7_SEEDS[0]}~{R7_SEEDS[1]} 는 쓰임으로만 쓴다)")
        return dict(use=use, seeds=[int(s) for s in seeds], steps=int(steps), world="N")
    if use not in USES:
        raise SystemExit(f"--use {use} 는 {', '.join(list(USES) + ['smoke'])} 가운데 하나다")
    if seeds or steps:
        raise SystemExit(f"--use {use} 의 시드·길이는 사전 등록 값이다 (--seeds·--steps 는 smoke 만)")
    lo, hi, n, world = USES[use]
    return dict(use=use, seeds=list(range(lo, hi + 1)), steps=int(n), world=world)


def smoke_plan(use: str, seeds, steps: int) -> dict:
    """도구 확인용(판정 아님): 쓰임 use 의 세계(N·G·끼임)를 스모크 시드·길이로. 시드는 SMOKE_SEEDS 안만 받는다."""
    p = use_plan("smoke", seeds, steps)
    p.update(use=f"smoke_{use}", world=USES[use][3])
    return p


def make_items(info: dict, spec: dict, plan: dict, probe: bool = False, tag: str = "x") -> list:
    """(종류, 꼬리표, 세계 job) 목록. N = G + 늑대 포만 끔(live.NOSAT), 두뇌 세계 키(spec sets), stuck = 끼임 세기(G). r6_eval.make_items 와 같은 꼴
    (도주 비용은 0 으로 고정이라 탐침에 넘기지 않는다)."""
    world = plan["world"]
    sets = dict(spec["sets"])
    if world == "N":
        sets.update(lv.NOSAT["sets"])
    if world == "stuck":
        jobs = ad.make_jobs(info, spec["path"], plan["seeds"], plan["steps"], False, dict(name=tag, sets=sets))
        for j in jobs:
            j.pop("log_every", None)
            j.pop("diag", None)
        return [("stuck", f"{tag}:stuck", j) for j in jobs]
    jobs = ad.make_jobs(info, spec["path"], plan["seeds"], plan["steps"], True, dict(name=tag, sets=sets))
    for j in jobs:
        j["horizons"] = [int(plan["steps"])]
        if probe:
            j["probe"] = dict(gamma=GAMMA)
    return [("probe" if probe else "multi", f"{tag}:{world}", j) for j in jobs]


def _r7_world(job: dict) -> dict:
    """세계 하나: live._world_multi 그대로(같은 세계·궤적·도망 기록) + 'gate'(판 5·6 세계의 막음 통계, 그 밖 None) + 탐침이면 'probe'(r6_eval._Probe).
    정책을 만드는 함수(rollout.build_policy)를 감싸 연결된 세계를 읽기만 한다."""
    from env_v2 import rollout as ro

    pr = job.pop("probe", None)
    holder: dict = {}
    orig = ro.build_policy

    def build(spec, seed=0):
        p = orig(spec, seed)
        if pr is not None:
            p = R6._Probe(p, float(pr.get("gamma", GAMMA)))
        holder["p"] = p
        return p

    ro.build_policy = build
    try:
        out = lv._world_multi(job)
    finally:
        ro.build_policy = orig
    p = holder["p"]
    w = p.world
    out["gate"] = w.flee_gate_stats() if getattr(w, "_fb", False) else None
    if pr is not None:
        out["probe"] = p.result()
    return out


def _r7_job(item):
    """워커에서 도는 일 하나: (종류, 꼬리표, 세계 job) → (꼬리표, 결과)."""
    kind, tag, job = item
    if kind in ("multi", "probe"):
        return tag, _r7_world(job)
    if kind == "stuck":
        return tag, ad._stuck_one(job)
    raise ValueError(f"모르는 일 {kind}")


def run_items(items: list, workers: int, label: str = "") -> list:
    """워커 풀(env_v2.rollout.make_executor)로 일을 돌린다 → [(꼬리표, 결과)] (items 순서). 50 개마다 진행 줄."""
    from concurrent.futures import as_completed

    from env_v2 import rollout as ro

    import r7_eval as R                       # 워커가 이름으로 불러올 수 있게 (스크립트로 돌 때 __main__ 이 아닌 모듈의 함수)

    fn = R._r7_job
    t0 = time.perf_counter()
    ex = ro.make_executor(min(int(workers), len(items)))
    out = [None] * len(items)
    if ex is None:
        for k, it in enumerate(items):
            out[k] = fn(it)
        return out
    with ex:
        futs = {ex.submit(fn, it): k for k, it in enumerate(items)}
        for n, f in enumerate(as_completed(futs), 1):
            out[futs[f]] = f.result()
            if n % 50 == 0 or n == len(items):
                print(f"  {label} {n}/{len(items)} ({time.perf_counter() - t0:.0f} 초)", flush=True)
    return out


def code_tags() -> dict:
    """셈 길 지문: 세계(live.eval_code_tag('python')), 이 도구와 불러 쓰는 R6 도구 파일 sha256 앞 16."""
    lv._CODE.pop("python", None)
    return dict(world=lv.eval_code_tag("python"), tool=hashlib.sha256(HERE.read_bytes()).hexdigest()[:16],
                tool_r6=hashlib.sha256(Path(R6.__file__).read_bytes()).hexdigest()[:16])


def run_model(info: dict, text: str, plan: dict, workers: int, probe: bool = False, name: str = "") -> dict:
    """한 두뇌 · 한 쓰임 → {meta, worlds} (끼임은 {meta, summary})."""
    import stuck_check

    spec = resolve_model(text)
    items = make_items(info, spec, plan, probe, tag=spec["label"])
    t0 = time.perf_counter()
    rows = run_items(items, workers, name or spec["label"])
    meta = dict(name=name, use=plan["use"], world=plan["world"], seeds=plan["seeds"], steps=plan["steps"], regions=sorted(info["regions"]),
                model=text, model_path=lv.path_text(spec["path"]), model_sha1=hashlib.sha1(Path(spec["path"]).read_bytes()).hexdigest()[:12],
                obs=spec["obs"], mask=spec["mask"], sets=spec["sets"], probe=bool(probe), snapshot=R6.SNAPSHOT.name, code=code_tags(),
                wall_s=round(time.perf_counter() - t0, 1), workers=int(workers))
    if plan["world"] == "stuck":
        return dict(meta=meta, summary=stuck_check.summarize([r for _, r in rows]))
    return dict(meta=meta, worlds=[r for _, r in rows])


load, save = R6.load, R6.save


def same_meta(path: Path, want: dict) -> bool:
    """이미 있는 판 파일이 같은 두뇌(sha1)·쓰임·시드·길이·세계 키·탐침·셈 길로 잰 것인가 (점검·고르기·판정 이어 돌리기)."""
    if not path.exists():
        return False
    m = load(path).get("meta") or {}
    return all(m.get(k) == want.get(k) for k in ("use", "seeds", "steps", "model_sha1", "sets", "probe", "code"))


def ensure_run(info, text, use, workers, name, out_dir=OUT, probe=False, plan=None) -> dict:
    """판 파일이 같은 조건으로 이미 있으면 읽고, 없으면 돌려 쓴다."""
    plan = plan or use_plan(use)
    spec = resolve_model(text)
    path = Path(out_dir) / f"{name}.json"
    want = dict(use=plan["use"], seeds=plan["seeds"], steps=plan["steps"], model_sha1=hashlib.sha1(Path(spec["path"]).read_bytes()).hexdigest()[:12],
                sets=spec["sets"], probe=bool(probe), code=code_tags())
    if same_meta(path, want):
        print(f"  {name}: 같은 조건의 판이 있다 — 다시 쓴다 ({lv.path_text(path)})", flush=True)
        return load(path)
    print(f"  {name}: {text} (판 {spec['mask']}) · {plan['use']} 시드 {plan['seeds'][0]}~{plan['seeds'][-1]} × 지역 {len(info['regions'])} × {plan['steps']} 스텝"
          f"{' · 탐침' if probe else ''}", flush=True)
    res = run_model(info, text, plan, workers, probe, name)
    save(res, path)
    return res


def prepare_info(out: Path = OUT) -> dict:
    """스냅숏 → <out>/world (r6_eval.prepare_info 와 같은 세계 — live.prepare)."""
    return R6.prepare_info(out)


# --------------------------------------------------------------------- #
# 막음 통계·길 기록·GF·GR
# --------------------------------------------------------------------- #

def gate_pooled(res: dict) -> dict | None:
    """판 전체 막음 통계 합(판 5·6 세계): free_decisions(덮기 밖 결정, 산 사슴)·brain_flee(그 가운데 두뇌 FLEE — 마스크가 막아 0 이어야 한다).
    막음 통계가 없는 세계(판 2·4)가 하나라도 있으면 None."""
    gs = [w.get("gate") for w in res["worlds"]]
    if not gs or any(g is None for g in gs):
        return None
    return dict(free_decisions=int(sum(g["free_decisions"] for g in gs)), brain_flee=int(sum(g["brain_flee"] for g in gs)), worlds=len(gs))


def none_seed(res: dict) -> dict | None:
    """시드 → 두뇌 스스로 뛴 도망 수(도망 길 none — 반사 스텝이 하나도 없는 도망, judge_notes 와 같은 셈, 지역 셋 합). 길 기록이 없는 판이면 None."""
    out: dict = {}
    for w in res["worlds"]:
        r = (w.get("flight") or {}).get("route")
        if r is None:
            return None
        n = (r.get("by_route", {}).get("none") or {}).get("n") or {}
        out[int(w["seed"])] = out.get(int(w["seed"]), 0) + int(sum(n.values()))
    return out


def gf_pair(cand: dict, cur: dict) -> dict:
    """GF 짝: 시드마다 1000 산 사슴-스텝당 시작한 도망(지역 셋 합), 후보 − 기준 (live.flight_rate_pair 'starts' — 판정 GF 와 같은 셈)."""
    return lv.flight_rate_pair(cand, cur, "starts")


def gr_pair(cand: dict, cur: dict) -> dict | None:
    """GR 짝: 시드마다 살아 끝난 도망 뒤 5 초(38 스텝) 안 다시 시작한 도망 수(지역 셋 합 — r6_eval.route_seed, 판정 GR 과 같은 셈), 후보 − 기준.
    두 판 가운데 길 기록이 없는 세계가 있으면(대조 '길 끔' 판 6) None — 세지 않는다."""
    a, b = R6.route_seed(cand), R6.route_seed(cur)
    if not all(x["route"] for x in list(a.values()) + list(b.values())):
        return None
    return re_.paired({s: float(v["refled"]) for s, v in a.items()}, {s: float(v["refled"]) for s, v in b.items()})


_ok_t = R6._ok_t


# --------------------------------------------------------------------- #
# 본 학습 2M·5M 점검 (사전 등록 5절)
# --------------------------------------------------------------------- #

def early_check(run: dict, base: dict, lam: float = LAM) -> dict:
    """점검 하나 (사전 등록 5-1): run = 점검 체크포인트 판(판 5 R7 · 판 6 대조), base = route0 판 (같은 점검 시드, 둘 다 --probe). lam = 학습 GAE λ
    ((b) 의 수익 목표 — R7 은 0.98 고정). 길 결정은 판 5 만 있다(판 6 대조는 (a)·GR 을 보지 않는다).
    (a) |π′(SHELTER) − route0| > 0.05, (b) 도주 스텝 설명 분산(λ-수익 목표) > 0,
    (c) 숨음 비율 짝 t > −2 · 잡힘 비율 짝 t < +2 · 잡힌 몫 짝 t < +2 · GF 짝 t < +2 · GR 짝 t < +2 (R7 — GF·GR 을 더했다),
    결함 = 얼기·잠 몫 > 0 또는 COVER 칸 확률 > 0 또는 마스크 밖 SHELTER > 0 또는 반사 밖 두뇌 FLEE(막음 통계 brain_flee) > 0.
    보고만: 몬테카를로 수익(λ 1)의 설명 분산, R5 점검 칸, 두뇌 스스로 뛴 도망(길 none) 수, 막음 통계."""
    if sorted((w["seed"], w["region"]) for w in run["worlds"]) != sorted((w["seed"], w["region"]) for w in base["worlds"]):
        raise ValueError("점검 판과 기준 판의 세계가 다르다")
    lk = R6.lam_key(lam)
    if float(lam) not in R6.EV_LAMS[:-1]:
        raise ValueError(f"(b) 의 λ {lam} 는 {R6.EV_LAMS[:-1]} 가운데 하나다")
    mask = int(run["meta"].get("mask", 0))
    if mask not in (5, 6):
        raise ValueError(f"점검 판의 두뇌는 판 5(R7)·6(대조)이어야 한다 — 판 {mask}")
    route = mask == 5
    pr, pb = R6.probe_pooled(run), R6.probe_pooled(base)
    E = EARLY
    if route:
        moved = pr["pe_shelter"] - pb["pe_shelter"]
        a_ok = bool(pr["two_n"] > 0 and math.isfinite(moved) and abs(moved) > E["pi_move"])
        a = dict(ok=a_ok, pe=pr["pe_shelter"], pe_start=pb["pe_shelter"], moved=moved, pi=pr["pi_shelter"], two_n=pr["two_n"],
                 rule=f"|π′(SHELTER) − route0| > {E['pi_move']:g} (SHELTER 가 열린 길 결정 {pr['two_n']} 개)")
    else:
        a = dict(ok=None, rule="대조 '길 끔' — 길 결정이 없다 (보지 않는다)")
    ev, mc = pr["ev"][lk], pr["ev"][R6.lam_key(1.0)]
    b = dict(ok=bool(pr["ev_n"] >= 2 and math.isfinite(ev) and ev > E["ev_min"]), ev=ev, ev_start=pb["ev"][lk], lam=float(lam), n=pr["ev_n"],
             ev_mc=mc, ev_mc_start=pb["ev"][R6.lam_key(1.0)],
             rule=f"도주 스텝 가치망 설명 분산(λ {lam:g} λ-수익 목표) > {E['ev_min']:g} (표본 {pr['ev_n']})")
    hide, cr = lv.hide_pair(run, base, "hide"), lv.hide_pair(run, base, "caught")
    gn = re_.paired(re_.per_seed(run, "caught"), re_.per_seed(base, "caught"))
    gf, gr = gf_pair(run, base), gr_pair(run, base)
    parts = dict(hide=dict(hide, ok=_ok_t(hide, hide["t"] > E["t_hide"])), caught_ratio=dict(cr, ok=_ok_t(cr, cr["t"] < E["t_caught_ratio"])),
                 caught=dict(gn, ok=_ok_t(gn, gn["t"] < E["t_caught"])), gf=dict(gf, ok=_ok_t(gf, gf["t"] < E["t_gf"])))
    if gr is not None:
        parts["gr"] = dict(gr, ok=_ok_t(gr, gr["t"] < E["t_gr"]))
    elif route:
        parts["gr"] = dict(ok=False, rule="길 기록이 없는 세계가 있다 — 판 5 점검 판·route0 기준 판은 길 기록이 있어야 한다 (통과로 두지 않는다)")
    else:
        parts["gr"] = dict(ok=None, rule="대조 '길 끔'(판 6) — 길 기록이 없어 GR 을 세지 않는다")
    c = dict(ok=all(v["ok"] for v in parts.values() if v["ok"] is not None), parts=parts,
             rule=(f"숨음 비율 짝 t > {E['t_hide']:+g} · 잡힘 비율 짝 t < +{E['t_caught_ratio']:g} · 잡힌 몫 짝 t < +{E['t_caught']:g} · "
                   f"GF 짝 t < +{E['t_gf']:g} · GR 짝 t < +{E['t_gr']:g} (route0 대비)"))
    pa, pbp = re_.pooled(run), re_.pooled(base)
    rt = R6.route_pooled(run) if route else None
    gate = gate_pooled(run)
    if gate is None:
        raise ValueError("점검 판에 막음 통계(gate)가 없다 — 판 5·6 두뇌를 이 도구(r7_eval)로 돌린다")
    defect = dict(freeze_sleep=pa["beh"]["freeze"] + pa["beh"]["sleep"], cover_max=pr["cover_max"], bad_shelter=(rt or {}).get("bad_shelter", 0),
                  gate_flee=gate["brain_flee"])
    defect["hit"] = bool(defect["freeze_sleep"] > 0 or defect["cover_max"] > 0 or defect["bad_shelter"] > 0 or defect["gate_flee"] > 0)
    starve_lim = 1.5 * pbp["starved"] if pbp["starved"] > 0 else 0.01
    report = dict(flee=(pa["beh"]["flee"], pbp["beh"]["flee"], pa["beh"]["flee"] < 0.5 * pbp["beh"]["flee"]),
                  shelter=(pa["shelter"], pbp["shelter"], pa["shelter"] > 3.0 * pbp["shelter"]),
                  starved=(pa["starved"], pbp["starved"], pa["starved"] > starve_lim))
    nr, nb = none_seed(run), none_seed(base)
    return dict(route=route, mask=mask, a=a, b=b, c=c, defect=defect, passed=bool((a["ok"] is not False) and b["ok"] and c["ok"] and not defect["hit"]),
                probe=pr, probe_base=pb, route_stats=rt, pooled=pa, pooled_base=pbp, report_r5=report, gate=gate,
                none=None if nr is None else int(sum(nr.values())), none_base=None if nb is None else int(sum(nb.values())),
                hide_share=lv.flight_pooled(run)["hide_share"], hide_share_base=lv.flight_pooled(base)["hide_share"])


def fmt_check(tag: str, r: dict) -> str:
    def yn(x):
        return "—" if x is None else ("통과" if x else "걸림")

    a, b, c = r["a"], r["b"], r["c"]
    lines = [f"{tag}: {'통과' if r['passed'] else '못 넘음'}" + (" · 결함" if r["defect"]["hit"] else "")]
    if r["route"]:
        lines.append(f"  (a) {yn(a['ok'])}: π′(SHELTER) {a['pe']:.4f} (route0 {a['pe_start']:.4f}, 차이 {a['moved']:+.4f}), π {a['pi']:.4f}, 두 칸 결정 {a['two_n']}")
    else:
        lines.append(f"  (a) —: {a['rule']}")
    lines.append(f"  (b) {yn(b['ok'])}: 도주 스텝 설명 분산(λ {b['lam']:g}) {b['ev']:+.4f} (route0 {b['ev_start']:+.4f}, 표본 {b['n']}) · 보고만 몬테카를로 "
                 f"{b['ev_mc']:+.4f} (route0 {b['ev_mc_start']:+.4f})")
    for k, nm in (("hide", "숨음 비율"), ("caught_ratio", "잡힘 비율"), ("caught", "잡힌 몫"), ("gf", "GF 1000 산 사슴-스텝당 시작한 도망"),
                  ("gr", "GR 5 초 안 다시 도망(시드당)")):
        q = c["parts"][k]
        if "diff" not in q:
            lines.append(f"  (c) {nm} {yn(q['ok'])}: {q['rule']}")
            continue
        fmt = ".4f" if k != "gr" else ".1f"
        lines.append(f"  (c) {nm} {yn(q['ok'])}: {q['a']:{fmt}} 대 route0 {q['b']:{fmt}} (차이 {q['diff']:+{fmt}}, t {lv.tfmt(q['t'])}, 시드 {q['n']})")
    d = r["defect"]
    lines.append(f"  결함 {'있음' if d['hit'] else '없음'}: 얼기·잠 몫 {d['freeze_sleep']:.4g}, COVER 확률 최대 {d['cover_max']:.3g}, 마스크 밖 SHELTER {d['bad_shelter']}, "
                 f"반사 밖 두뇌 FLEE {d['gate_flee']} (덮기 밖 결정 {r['gate']['free_decisions']:,})")
    if r["route_stats"]:
        s = r["route_stats"]
        lines.append(f"  길: 결정 {s['decisions']} · SHELTER 고름 {s['picked_shelter']} (몫 {s['shelter_share']:.4f}) · 다시 고름 {s['redecide_feas']} · 무효 {s['invalid_shelter']}")
    lines.append(f"  보고만: 두뇌 스스로 뛴 도망(길 none) {'—' if r['none'] is None else r['none']} (route0 {r['none_base']}) · "
                 + " · ".join(f"{k} {x:.4f} (route0 {y:.4f}{' — R5 규칙이면 걸림' if hit else ''})" for k, (x, y, hit) in r["report_r5"].items()))
    return "\n".join(lines)


def main_check_rules(checks: dict, at: list[int]) -> dict:
    """본 학습 점검 모음 (사전 등록 5-2). checks = {(시드 이름, k): early_check} (시드 이름 's0'·'s1'·'s2' — 대조 'off' 는 넣지 않는다).
    제외 = (c)(숨음 비율·잡힘 비율·잡힌 몫·GF·GR) 가 2M·5M 가운데 한 번이라도 걸린 시드. 멈춤 = 결함 · 마지막 점검에서 모든 시드 (a) 안 움직임 ·
    남은 시드 모두 (b) 걸림 · 모든 시드 제외."""
    seeds = sorted({s for s, _ in checks if s != "off"})
    out: dict = dict(excluded={}, stop=False, why=[], defect=False)
    for s in seeds:
        bad = []
        for (ss, k), v in sorted(checks.items(), key=lambda kv: kv[0][1]):
            if ss == s and not v["c"]["ok"]:
                parts = [nm for nm, q in v["c"]["parts"].items() if q["ok"] is False]
                bad.append(f"{k}M (c) {'·'.join(parts)}")
        if bad:
            out["excluded"][s] = "(c) 걸림: " + ", ".join(bad)
    if any(v["defect"]["hit"] for v in checks.values()):
        out.update(stop=True, defect=True)
        out["why"].append("결함(얼기·잠·COVER·마스크 밖 SHELTER·반사 밖 두뇌 FLEE) — 모든 학습을 멈추고 고친다")
    k_last = max(at)
    last = {s: checks.get((s, k_last)) for s in seeds}
    if all(v is not None for v in last.values()) and last:
        if not any(v["a"]["ok"] for v in last.values()):
            out["stop"] = True
            out["why"].append(f"{k_last}M 에서 모든 시드가 (a) 에서 움직이지 않았다 — '못 배움' (R7 실패로 보고)")
        live = [s for s in seeds if s not in out["excluded"]]
        if live and all(not last[s]["b"]["ok"] for s in live):
            out["stop"] = True
            out["why"].append(f"{k_last}M 에서 남은 시드 모두 (b) 걸림 — 멈추고 사람에게 묻는다")
    if seeds and len(out["excluded"]) == len(seeds):
        out["stop"] = True
        out["why"].append("모든 R7 시드가 (c) 로 빠졌다 — R7 실패로 보고 (고르기·판정을 하지 않는다)")
    return out


# --------------------------------------------------------------------- #
# 고르기 (사전 등록 6절)
# --------------------------------------------------------------------- #

FINAL_RE = r"^v3_r7_g995_s(\d+)_20m$"                 # 고르기 후보 = R7 본 학습의 마지막 모델만 (중간 체크포인트·대조는 받지 않는다)


CHECK_AT = (2, 5)                                    # 본 학습 점검 체크포인트(백만 스텝 — 사전 등록 5절)


def select_guard(models: list, early_main: Path | None = None) -> None:
    """사전 등록 6절 막기: 후보는 R7 본 학습의 마지막 모델(v3_r7_g995_s<s>_20m.zip)만, 본 학습 점검(logs/early_main.json)이 제외한 시드는 받지 않는다.
    점검 기록이 없거나(스모크 기록 포함), 멈춤이거나, 그 시드의 2M·5M 점검 줄이 없으면 멈춘다(R7 은 점검이 GF·GR 로 시드를 뺀다 — 기록 없이 고르지 않는다)."""
    early_main = HERE.parent / "logs" / "early_main.json" if early_main is None else Path(early_main)
    if not early_main.exists():
        raise SystemExit(f"{lv.path_text(early_main)} 이 없다 — 본 학습 2M·5M 점검(early_checks.py)을 먼저 끝낸다 (사전 등록 5-2·6절)")
    d = json.loads(early_main.read_text(encoding="utf-8"))
    if d.get("smoke"):
        raise SystemExit(f"{lv.path_text(early_main)} 은 스모크 기록이다 — 본 학습 점검 기록이 아니다")
    rules, rows = d.get("rules") or {}, d.get("rows") or {}
    if rules.get("stop"):
        raise SystemExit(f"본 학습 점검이 멈춤이다 — {' / '.join(rules.get('why') or [])} (사전 등록 5-2 — 고르지 않는다)")
    excluded = rules.get("excluded") or {}
    for m in models:
        stem = Path(m).stem
        hit = re.match(FINAL_RE, stem)
        if not hit:
            raise SystemExit(f"고르기 후보 {m} 는 R7 본 학습의 마지막 모델(v3_r7_g995_s<시드>_20m.zip)이 아니다 (사전 등록 6절)")
        s = f"s{hit.group(1)}"
        if s in excluded:
            raise SystemExit(f"{m}: 본 학습 점검이 제외한 시드다 — {excluded[s]} ({lv.path_text(early_main)}, 사전 등록 5-2)")
        miss = [f"{k}M" for k in CHECK_AT if not rows.get(f"{s}_{k}m") or rows[f"{s}_{k}m"].get("missing")]
        if miss:
            raise SystemExit(f"{m}: 본 학습 점검 {', '.join(miss)} 기록이 없다 ({lv.path_text(early_main)}) — 점검을 마친 시드만 고른다 (사전 등록 5-2·6절)")


def select_rule(rows: list, base: dict) -> dict:
    """고르기 (사전 등록 6절). rows = [(모델 글, 모델 시드, 판)], base = route0 같은 고르기 시드 판.
    자격: GF 짝 t < +2.0 이고 GR 짝 t < +2.0 (route0 대비, 고르기 시드 20 짝). 자격 있는 모델 가운데 숨음 비율(쫓긴 도망 가운데, 전체 합) 큰 쪽 →
    잡힌 몫 작은 쪽 → 굶은 몫 작은 쪽 → 모델 시드 작은 쪽(r6_eval.select_key). 자격 있는 모델이 없으면 pick None(R7 실패로 보고 — 판정하지 않는다)."""
    out = []
    for m, seed, res in rows:
        gf, gr = gf_pair(res, base), gr_pair(res, base)
        gf_ok = _ok_t(gf, gf["t"] < SELECT["t_gf"])
        gr_ok = gr is not None and _ok_t(gr, gr["t"] < SELECT["t_gr"])
        out.append(dict(model=m, seed=int(seed), key=R6.select_key(res, seed), gf=gf, gr=gr, ok=bool(gf_ok and gr_ok), gf_ok=gf_ok, gr_ok=gr_ok))
    ok = sorted([r for r in out if r["ok"]], key=lambda r: r["key"])
    return dict(rows=out, eligible=[r["model"] for r in ok], pick=ok[0]["model"] if ok else None, base_key=R6.select_key(base, -1),
                rule=f"자격 GF 짝 t < +{SELECT['t_gf']:g} · GR 짝 t < +{SELECT['t_gr']:g} (route0 대비) → 숨음 비율 큰 쪽 → 잡힌 몫 → 굶은 몫 → 모델 시드")


def picked_model(select_txt: Path | None = None) -> str | None:
    """logs/select.txt 끝의 '고른 모델: …' (없거나 '없음' 이면 None)."""
    p = HERE.parent / "logs" / "select.txt" if select_txt is None else Path(select_txt)
    if not p.exists():
        return None
    for line in reversed(p.read_text(encoding="utf-8").splitlines()):
        if line.startswith("고른 모델: "):
            v = line[len("고른 모델: "):].strip()
            return None if v.startswith("없음") else v
    return None


# --------------------------------------------------------------------- #
# 판정 (사전 등록 4절)
# --------------------------------------------------------------------- #

def a5_check(model: Path, out_dir: Path = BRAINS) -> dict:
    """내보내기 확인 A5: 두뇌 파일을 쓰고(export_weights_v3.export_brain_file — 판 5 두뇌면 골든 세계 = 판 5 거울) 다시 읽어 확인(adapt.verify_brain_file:
    가중치 sha256·골든 로짓 오차 ≤ 허용·행동 같음·유한) + 계약(관측 24·판 5·해시 0xad7bad5e1acaf071)."""
    import export_weights_v3 as ex

    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"{Path(model).stem}.json"
    d = ex.export_brain_file(Path(model), f)
    v = ad.verify_brain_file(f)
    v["contract_ok"] = bool(str(d.get("contract_hash")) == CONTRACT_R7 and int(d.get("obs_dim", 0)) == 24 and int(d.get("mask_version", 0)) == 5)
    v.update(contract_hash=str(d.get("contract_hash")), obs_dim=int(d.get("obs_dim", 0)), mask_version=int(d.get("mask_version", 0)),
             golden_world=(d.get("golden") or {}).get("world_config"))
    v["ok"] = bool(v["ok"] and v["finite"] and v["contract_ok"])
    return v


GUARDS = R6.GUARDS                                   # 지킴 18 칸 — R6 그대로


def compare(cand: dict, other: dict, base: dict | None = None) -> dict:
    """보고만: 후보(R7) − 다른 판(같은 N 판정 시드). 숨음 비율·잡힘 비율·잡힌 몫·쫓긴 시간·GF·GR(두 판 모두 길 기록이 있을 때만). base(route0)를 주면
    그 판의 route0 대비 GF·GR 도 적는다."""
    out = dict(hide=lv.hide_pair(cand, other, "hide"), caught_ratio=lv.hide_pair(cand, other, "caught"),
               caught=re_.paired(re_.per_seed(cand, "caught"), re_.per_seed(other, "caught")), chase=lv.flight_pair(cand, other),
               gf=gf_pair(cand, other), gr=gr_pair(cand, other), flight=lv.flight_pooled(other), meta=other.get("meta"))
    if base is not None:
        out["vs_route0"] = dict(gf=gf_pair(other, base), gr=gr_pair(other, base))
    return out


def judge(N: dict, G: dict, stuck: dict, a5: dict | None, others: dict | None = None) -> dict:
    """R7 판정 (사전 등록 4절). N·G = {'candidate': R7 판, 'current': route0 판}, stuck = {'candidate', 'current'} 끼임 판. a5 = a5_check 결과(None 이면
    A5 를 통과로 두지 않는다). others = {'off': 대조 '길 끔' 판, 'rule': '늘 SHELTER' 판, 'r6': R6 고른 두뇌 판} (같은 N 판정 시드 — 보고만).
    1차 P1 = live.gate_live 의 P1_N_hide (숨음 비율 짝 차이 > 0 ∧ t ≥ +t_crit(n₁ − 1) — n₁ 100 이면 +1.984), 지킴 = GH·GN·GF·GV·GC(live.gate_live) +
    GT·GTr·GR(r6_eval.route_guards) + GG·G4·G5·G6(live.gate_live) + A5 — R6 판정과 같은 셈이다."""
    g = lv.gate_live(dict(N=N, G=G), stuck, None, hide_min_effect=0.0)   # PREREG δ 0 (LIVE 값 0.01 은 실시간 고리 것 — 10-27 (10))
    c = {k: v for k, v in g["criteria"].items() if k != "R_check"}
    c.update(R6.route_guards(N["candidate"], N["current"]))
    c["A5_export"] = (dict(a5, rule="두뇌 파일 다시 읽기: sha256·골든 로짓 오차 ≤ 허용·행동 같음·유한·관측 24·판 5·계약 0xad7bad5e1acaf071")
                      if a5 is not None else dict(ok=False, rule="A5 를 하지 않았다 (통과로 두지 않는다)"))
    p1 = c["P1_N_hide"]
    bad = [k for k in GUARDS if c.get(k, {}).get("ok") is not True]
    if not p1["ok"]:
        verdict, why = "기각", f"1차 P1 실패: 숨음 비율 R7 {lv.pct(p1['a'], 2)} 대 route0 {lv.pct(p1['b'], 2)} (짝 t {lv.tfmt(p1['t'])}, 시드 {p1['n']})"
    elif bad:
        verdict, why = "기각", "지킴 실패: " + ", ".join(bad)
    else:
        verdict, why = "통과", "1차 P1(숨음 비율)·지킴 모두 통과"
    nc, nb = none_seed(N["candidate"]), none_seed(N["current"])
    rep: dict = dict(chase=c.pop("REPORT_N_chase", None), flight={w: g["report"]["flight"][w] for w in ("N", "G")},
                     pooled_N=g["report"]["pooled_N"], pooled_G=g["report"]["pooled_G"],
                     route=dict(candidate=R6.route_pooled(N["candidate"]), current=R6.route_pooled(N["current"])),
                     chase_decomp=R6.chase_decomp(N["candidate"], N["current"]), regions={},
                     gate=dict(N=gate_pooled(N["candidate"]), G=gate_pooled(G["candidate"])),
                     none=dict(candidate=None if nc is None else int(sum(nc.values())), current=None if nb is None else int(sum(nb.values())),
                               seeds=len(nc or {})))
    for r in REGIONS:
        a, b = R6.region_res(N["candidate"], r), R6.region_res(N["current"], r)
        if not a["worlds"]:
            continue
        rep["regions"][r] = dict(hide=lv.hide_pair(a, b, "hide"), caught_ratio=lv.hide_pair(a, b, "caught"),
                                 caught=re_.paired(re_.per_seed(a, "caught"), re_.per_seed(b, "caught")), gf=gf_pair(a, b), gr=gr_pair(a, b),
                                 route=R6.route_pooled(a))
    for name, other in (others or {}).items():
        if other is not None:
            rep[name] = compare(N["candidate"], other, N["current"])
    return dict(verdict=verdict, passed=verdict == "통과", why=why, criteria=dict(P1_N_hide=p1, **{k: c[k] for k in GUARDS if k in c}),
                n=g["n"], t_crit=g["t_crit"], n_g=g["n_g"], t_crit_g=g["t_crit_g"], n_flight=g["n_flight"], t_crit_flight=g["t_crit_flight"],
                dropped_flight=g["dropped_flight"], report=rep, early=EARLY, select=SELECT)


def _q(q: dict | None, scale: float = 1.0, unit: str = "", nd: int = 2) -> str:
    if q is None:
        return "— (길 기록 없음)"
    return f"{q['diff'] * scale:+.{nd}f}{unit} (t {lv.tfmt(q['t'])})"


def fmt_judge(res: dict, head: str = "") -> str:
    L = [f"# R7 판정 — {res['verdict']}" + (f" ({head})" if head else ""), "",
         f"- {res['why']}",
         f"- N 시드 {res['n']} (문턱 t_crit {res['t_crit']:.3f}), 숨음 비율 짝 시드 {res['n_flight']} (문턱 {res['t_crit_flight']:.3f}, 빠진 시드 "
         f"{res['dropped_flight']}), G 시드 {res['n_g']} (문턱 {res['t_crit_g']:.3f})", "",
         "| 기준 | R7 | route0 | 차이 | t | 규칙 | 통과 |", "|---|---|---|---|---|---|---|"]
    for k, v in res["criteria"].items():
        a, b, d, t = R6._cell(k, v)
        L.append(f"| {k} | {a} | {b} | {d} | {t} | {v.get('rule', '')} | {'예' if v.get('ok') else '아니오'} |")
    rep = res["report"]
    L += ["", "## 보고만 (판정에 쓰지 않음)", ""]
    ch = rep.get("chase")
    if ch:
        L.append(f"- N 쫓긴 시간(스스로 벗어난 도망, 시드 평균): R7 {ch['a']:.3f} 초 · route0 {ch['b']:.3f} 초 (차이 {ch['diff']:+.3f}, t {lv.tfmt(ch['t'])}, 시드 {ch['n']})")
    dc = rep["chase_decomp"]
    L.append(f"- 쫓긴 시간 전체 합 차이 {dc['total']:+.3f} 초 = 끝 까닭 섞임 {dc['mix']:+.3f} + 같은 까닭 안 {dc['within']:+.3f}")
    for w in ("N", "G"):
        f = rep["flight"][w]
        for who in ("candidate", "current"):
            x = f[who]
            L.append(f"- {w} {('R7' if who == 'candidate' else 'route0')}: 쫓긴 도망 {x['chased']} · 숨음 {x['hidden']} ({lv.pct(x['hide_share'], 2)}) · "
                     f"잡힘 비율 {lv.pct(x['caught_share_chased'], 2)} · 은신처 끝 뒤 10 초 안 잡힘 {x['cover_then_caught']} · 굶음 {x['cover_then_starved']} · "
                     f"지켜보는 중 판 끝 {x['watching']}")
    for who in ("candidate", "current"):
        s = rep["route"][who]
        L.append(f"- 길 ({'R7' if who == 'candidate' else 'route0'}, N): SHELTER 몫 {s['shelter_share']:.4f} · 도망 하나당 결정 {s['per_flight_decisions']:.3f} · "
                 f"다시 고름 {s['per_flight_redecide']:.4f} · 무효 {s['per_flight_invalid']:.4f} · 길 바꿈 {s['per_flight_switches']:.4f}")
    gt = rep["gate"]
    for w in ("N", "G"):
        x = gt[w]
        if x is not None:
            L.append(f"- 막음 통계 ({w}, R7): 덮기 밖 결정 {x['free_decisions']:,} · 그 가운데 두뇌 FLEE {x['brain_flee']} (마스크가 막아 0 이어야 한다)")
    nn = rep["none"]
    L.append(f"- 두뇌 스스로 뛴 도망(길 none, N 판 전체 — 시드 {nn['seeds']}): R7 {nn['candidate']} · route0 {nn['current']}")
    L += ["", "| 지역 | 숨음 비율 R7 − route0 (t) | 잡힘 비율 (t) | 잡힌 몫 (t) | GF (t) | GR 시드당 (t) | R7 SHELTER 몫 |", "|---|---|---|---|---|---|---|"]
    for r, x in rep["regions"].items():
        L.append(f"| {r} | {_q(x['hide'], 100, '%p')} | {_q(x['caught_ratio'], 100, '%p')} | {_q(x['caught'], 100, '%p')} | {_q(x['gf'], 1, '', 4)} | "
                 f"{_q(x['gr'], 1, '', 1)} | {x['route']['shelter_share']:.4f} |")
    L.append("")
    for name, label in (("off", "대조 '길 끔'"), ("rule", "손 규칙 '늘 SHELTER'"), ("r6", "R6 고른 두뇌")):
        x = rep.get(name)
        if x is None:
            continue
        L.append(f"- R7 − {label}: 숨음 비율 {_q(x['hide'], 100, '%p')} · 잡힘 비율 {_q(x['caught_ratio'], 100, '%p')} · 잡힌 몫 {_q(x['caught'], 100, '%p')} · "
                 f"쫓긴 시간 {_q(x['chase'], 1, ' 초', 3)} · GF {_q(x['gf'], 1, '', 4)} · GR {_q(x['gr'], 1, '/시드', 1)} "
                 f"(그 판의 숨음 비율 {lv.pct(x['flight']['hide_share'], 2)})")
        v0 = x.get("vs_route0")
        if v0:
            L.append(f"  - {label} − route0: GF {_q(v0['gf'], 1, '', 4)} · GR {_q(v0['gr'], 1, '/시드', 1)}")
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def cmd_run(a) -> int:
    seeds = R6.parse_seeds(a.seeds) if a.seeds else None
    plan = use_plan(a.use, seeds, a.steps)
    info = prepare_info(a.out_dir)
    res = ensure_run(info, a.model, a.use, a.workers, a.name, a.out_dir, a.probe, plan)
    if "worlds" in res:
        p, f = re_.pooled(res), lv.flight_pooled(res)
        line = (f"{a.name}: 세계 {p['worlds']} · 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} · 쫓긴 도망 {f['chased']} 숨음 비율 "
                f"{lv.pct(f['hide_share'], 2)} 잡힘 비율 {lv.pct(f['caught_share_chased'], 2)} · 은신처 안 잡힘 {p['catch_cover']} · 시작한 도망 {f['started']}")
        g, nn = gate_pooled(res), none_seed(res)
        line += (f" · 막음 통계 {'—' if g is None else str(g['brain_flee']) + ' / 덮기 밖 결정 ' + format(g['free_decisions'], ',')}"
                 f" · 길 none 도망 {'—' if nn is None else sum(nn.values())}")
        if a.probe:
            q = R6.probe_pooled(res)
            line += (f" · π′(SHELTER) {q['pe_shelter']:.4f} (두 칸 결정 {q['two_n']}) · 도주 스텝 설명 분산 "
                     + " ".join(f"λ{k} {v:+.4f}" for k, v in q["ev"].items()) + f" (표본 {q['ev_n']})")
        print(line, flush=True)
    else:
        print(f"{a.name}: 끼임 {re_.stuck_counts(res)}", flush=True)
    return 0


def cmd_check(a) -> int:
    r = early_check(load(a.run), load(a.base), LAM)
    print(fmt_check(Path(a.run).stem, r))
    return 0 if r["passed"] else 1


def _smoke_plans(a) -> dict | None:
    """--smoke 시드 --smoke-steps 길이 → 쓰임마다 스모크 계획 (도구 확인 — 판정 아님). 없으면 None (사전 등록 계획)."""
    if not a.smoke:
        return None
    seeds = R6.parse_seeds(a.smoke)
    return {u: smoke_plan(u, seeds, a.smoke_steps) for u in USES}


def cmd_select(a) -> int:
    sp = _smoke_plans(a)
    plan = sp["select"] if sp else None
    if not sp:
        select_guard(a.models)
    info = prepare_info(a.out_dir)
    rows = []
    for m in a.models:
        spec = resolve_model(m)
        if spec["mask"] != 5:
            raise SystemExit(f"고르기 후보 {m} 는 마스크 판 {spec['mask']} 이다 — R7 두뇌(판 5)만 고른다")
        res = ensure_run(info, m, "select", a.workers, f"select_{spec['label']}", a.out_dir, plan=plan)
        rows.append((m, R6.model_seed_of(spec["label"]), res))
    base = ensure_run(info, "route0", "select", a.workers, "select_route0", a.out_dir, plan=plan)
    sel = select_rule(rows, base)
    lines = ["| 모델 | 숨음 비율(전체 합) | 잡힌 몫 | 굶은 몫 | GF 짝 차이 (t) | GR 짝 차이 시드당 (t) | 자격 |", "|---|---|---|---|---|---|---|"]
    for r in sorted(sel["rows"], key=lambda r: r["key"]):
        k = r["key"]
        lines.append(f"| {r['model']} | {lv.pct(-k[0], 2)} | {k[1]:.4f} | {k[2]:.4f} | {_q(r['gf'], 1, '', 4)} | {_q(r['gr'], 1, '', 1)} | "
                     f"{'예' if r['ok'] else '아니오 (' + ('GF' if not r['gf_ok'] else '') + (' GR' if not r['gr_ok'] else '') + ')'} |")
    bk = sel["base_key"]
    lines.append(f"| route0 (보고만) | {lv.pct(-bk[0], 2)} | {bk[1]:.4f} | {bk[2]:.4f} | | | |")
    lines += ["", f"규칙: {sel['rule']}", ""]
    lines.append(f"고른 모델: {sel['pick']}" if sel["pick"] else "고른 모델: 없음 — GF·GR 자격을 넘은 모델이 없다 (사전 등록 6절 — R7 실패로 보고, 판정하지 않는다)")
    text = "\n".join(lines)
    print(text)
    logs = Path(a.out_dir) if sp else HERE.parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "select.txt").write_text(text + "\n", encoding="utf-8")
    (logs / "select.json").write_text(json.dumps(lv.jsonable(sel), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return 0 if sel["pick"] else 1


def cmd_judge(a) -> int:
    sp = _smoke_plans(a) or {}
    if not sp:
        # 사전 등록 6·7절: 고른 모델 하나만 판정한다 (logs/select.txt 의 '고른 모델' 과 같은 파일이어야 한다)
        pk = picked_model()
        if pk is None:
            raise SystemExit("logs/select.txt 에 고른 모델이 없다 — 먼저 r7_eval.py select (사전 등록 6절. '없음' 이면 R7 실패로 보고 — 판정하지 않는다)")
        same = Path(resolve_model(pk)["path"]).resolve() == Path(resolve_model(a.model)["path"]).resolve()
        if not same:
            raise SystemExit(f"--model {a.model} 은 고른 모델 {pk} 가 아니다 (사전 등록 6·7절 — 고른 모델 하나만 판정한다)")
    spec = resolve_model(a.model)
    if spec["mask"] != 5:
        raise SystemExit(f"--model {a.model} 은 마스크 판 {spec['mask']} 이다 — R7 판정은 판 5 두뇌만 받는다")
    if a.off and resolve_model(a.off)["mask"] != 6:
        raise SystemExit(f"--off {a.off} 는 대조 '길 끔'(판 6) 두뇌가 아니다")
    info = prepare_info(a.out_dir)
    W = a.workers
    runs = {}
    for key, text, use, name in (("N_r7", a.model, "judge_n", "judge_r7_N"), ("N_base", "route0", "judge_n", "judge_route0_N"),
                                 ("G_r7", a.model, "judge_g", "judge_r7_G"), ("G_base", "route0", "judge_g", "judge_route0_G"),
                                 ("S_r7", a.model, "stuck", "stuck_r7"), ("S_base", "route0", "stuck", "stuck_route0")):
        runs[key] = ensure_run(info, text, use, W, name, a.out_dir, plan=sp.get(use))
    others = dict(off=ensure_run(info, a.off, "judge_n", W, "judge_off_N", a.out_dir, plan=sp.get("judge_n")) if a.off else None,
                  rule=None if a.no_rule else ensure_run(info, "shelter_rule", "judge_n", W, "judge_rule_N", a.out_dir, plan=sp.get("judge_n")),
                  r6=None if a.no_r6 else ensure_run(info, "r6", "judge_n", W, "judge_r6_N", a.out_dir, plan=sp.get("judge_n")))
    a5 = a5_check(spec["path"], Path(a.out_dir) / "brains" if sp else BRAINS)
    res = judge(dict(candidate=runs["N_r7"], current=runs["N_base"]), dict(candidate=runs["G_r7"], current=runs["G_base"]),
                dict(candidate=runs["S_r7"], current=runs["S_base"]), a5, others)
    res["models"] = dict(r7=a.model, base="route0", off=a.off, rule=None if a.no_rule else "shelter_rule", r6=None if a.no_r6 else lv.path_text(R6_PICK))
    text = fmt_judge(res, Path(a.model).name)
    print(text)
    out = Path(a.out) if a.out else (Path(a.out_dir) / "judge_smoke.md" if sp else HERE.parent / "judge.md")
    out.write_text(text + "\n", encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(lv.jsonable(res), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return 0 if res["passed"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--use", required=True)
    r.add_argument("--model", required=True, help="route0 · route0m5 · obs21zero · obs21zero_m6 · r6 · shelter_rule · 모델 zip")
    r.add_argument("--name", required=True)
    r.add_argument("--probe", action="store_true")
    r.add_argument("--seeds", default=None, help="smoke 만")
    r.add_argument("--steps", type=int, default=None, help="smoke 만")
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    c.add_argument("--base", required=True)
    s = sub.add_parser("select")
    s.add_argument("--models", nargs="+", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--model", required=True)
    j.add_argument("--off", default=None, help="대조 '길 끔' 모델 (판 6, 보고만)")
    j.add_argument("--no-rule", action="store_true", help="'늘 SHELTER' 보고 줄을 돌리지 않는다")
    j.add_argument("--no-r6", action="store_true", help="'R7 − R6' 보고 줄을 돌리지 않는다")
    j.add_argument("--out", default=None)
    for p in (r, s, j):
        p.add_argument("--workers", type=int, default=lv.default_workers())
        p.add_argument("--out-dir", type=Path, default=OUT)
    for p in (s, j):
        p.add_argument("--smoke", default=None, help="도구 확인: 스모크 시드(32080~32099 안)로 모든 쓰임을 돌린다 — 판정 아님")
        p.add_argument("--smoke-steps", type=int, default=300)
    a = ap.parse_args(argv)
    return dict(run=cmd_run, check=cmd_check, select=cmd_select, judge=cmd_judge)[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
