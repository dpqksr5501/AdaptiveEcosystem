"""두 길 두뇌 C++ 이식 판 단위 대조 자료 (이식 계획서 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-2, 설계
RL_V3_FLIGHT_ROUTE_DESIGN.md 16-12·16-14 단계 6 — C++ 은 RUN·SHELTER 기하만). 장면 단위 골든은 herbivore_rl/export_golden_v3_route.py →
AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/RouteGoldenVectorsV3.h (10-24 이식 때 Source 로 옮김) + 같은 내용 results/v3/route/port/RouteGoldenVectorsV3.json.
10-24 C++ 평가기 대조: results/v3/route/port/native_check.py 가 같은 일을 평가기(Tools/EcoV3Eval — 두 길 세계를 받는다)로 돌려 C++ trace 에 이 파일의
`digest_state` 를 걸어 traj/ 지문과, 세계 기록을 stats/ 의 record 와 견준다.

    # herbivore_rl/ 에서 (Anaconda base python, PYTHONUTF8=1). 결과 → results/v3/route/port/{brains,traj,stats}/ + MANIFEST.json
    python results/v3/route/port/make_traces.py [--workers 4]
    python results/v3/route/port/make_traces.py --check          # 올린 파일이 지금 코드로 다시 만든 것과 바이트까지 같은지만 본다 (쓰지 않는다)
    python results/v3/route/port/make_traces.py --steps 150 --only v3_obs24route_shelter2__N__Forest__34900 --out <폴더>     # 짧게 (시험)

세계 (계획서 10-2 — 10-22 파리티 검사와 같은 판, 판정 시드가 아니다): 스냅숏 results/v3/live/pilot/eco_v3_snapshot_s20004_t475_e1.json 의 판정 세계
(live.prepare → 관측 21 거울 바탕 + 스냅숏 지역 설정·먹이 지도, 부활 없음, 사슴 128·늑대 4, 숲 시야 끔 — 게임 기본) + 세계 덮기
features.wild_flight.route = true (관측 24·마스크 판 4) × 세계 N(늑대 포만 끔)·G(게임) × 지역 셋(Barren·Forest·Highland) × 시드 34900·34901 × 1800 스텝.
일(job)은 `ceval.py compare --world-set features.wild_flight.route=true` 와 같은 길(ceval.eval_items)로 만든다 — 이식 뒤 평가기는 같은 일을
ceval.native_job 으로 받는다(계획서 7-1). 파이썬 기록·궤적은 그 compare 의 파이썬 쪽과 같다: 기록 = adapt._world_one(r4_eval._one 칸), 궤적 =
ceval.python_trace 와 같은 스텝·같은 칸(+ 계획서 7-3 의 길 칸 route·route_k·route_age·route_feas·route_decide·route_req).

두뇌 (brains/ — 계획서 10-2):
  v3_r1_g995_s3_obs24route0.json  route0 = results/v3/route/brains 의 두뇌 파일 그대로 (모델 zip ckpt/v3/v3_r1_g995_s3_obs24route0.zip — 저장소 밖,
                                  results/v3/route/route_extend.py 가 만든다). 배포 결정은 늘 RUN (SHELTER 로짓 = RUN − 2).
  v3_obs24route_shelter2.json·.zip 늘 SHELTER 시험 두뇌 = route0 에서 출력층 칸 4 편향만 칸 1 + 2 (export_golden_v3_route.brain_model — 골든 기준 루프와
                                  같은 두뇌). 길 결정 줄 {RUN, SHELTER} 에서 SHELTER 가 열리면 늘 SHELTER(로짓 차 +2), 그 밖은 route0 과 같다(칸 4 는 허용이
                                  막는다). 길이 실제로 SHELTER 로 가는 경로(적용·유지·무효·은신처 도착 끝 도망·숨은 뒤 지켜보기)를 C++ 이 맞춰야 해서 둔다.
                                  학습·판정에 쓰지 않는다. zip 은 *.zip 무시 규칙으로 git 밖이다 — 이 스크립트가 같은 바이트로 다시 만든다.

궤적 지문 (traj/<두뇌>__<N|G>__<지역>__<시드>.jsonl.gz — gzip mtime 0): 첫 줄 = 머리 dict, 그 뒤 스텝 s = 0..T 마다 [s, 칸마다 sha256 앞 8 자리 16 진].
  스텝 s 상태 = ceval.python_trace 의 s 번째 줄 (0 = reset 직후, 그 상태의 관측으로 낸 다음 요청 포함). 칸 (`digest_state` — 리틀 엔디언 바이트, C 순서):
    clock  t i8 ‖ dark f8 ‖ pred_ema f8
    deer   x·y·hx·hy·energy·reserve (N) f8 — 모든 슬롯 (죽은 사슴은 죽은 자리에 멈춘다)
    fate   keep(덮기 wf_mode) (N) i4 ‖ cause(death_cause) (N) i4
    beh    behavior i4 — 스텝 첫머리에 산 슬롯 (alive0, s = 0 은 모두)
    obs    관측 24 f4 — alive0 슬롯 (행 우선)
    req    request(다음 요청) i4 — 스텝 끝 산 ∧ 덮기 < 2 슬롯 (ceval.trace_diff 와 같은 범위)
    kin    to_centroid·separation·away_from_pred·food_grad (N, 2) f8 — alive0 슬롯
    wolf   늑대 x·y·hx·hy f8 ‖ cd·sat·asleep·target i4 (s = 0 의 target 은 −1 — trace_diff 처럼 보지 않는다)
    route  route·route_k·route_age·route_feas·route_decide·route_req i4 — 스텝 끝 산 슬롯 (route_req = 길 결정(route_decide ∧ 도주) 사슴의 두뇌 출력,
           아니면 −1. 스텝 끝 `_wf_update` 뒤·다음 스텝 `_route_apply` 앞 — C++ 은 H 뒤·다음 A 앞)
  C++ trace(계획서 7-2 의 WriteState 확장)를 ceval 이 읽은 dict 에 같은 `digest_state` 를 걸면 스텝·칸마다 견줄 수 있다(첫 갈림 칸을 바로 안다).
세계 기록 (stats/<같은 이름>.json): record = ceval compare 파이썬 쪽 기록(adapt._world_one — wall_s 뺌, flight.route·flight.hide·flight.episode(10-24 쫓김 사건) 포함), trace = 궤적 판
  끝(잡힘·굶음·산·도망 기록이 record 와 같은지·repertoire_stats — decide_frac), check = 두뇌 파일 순전파(numpy float32)와 torch argmax 가 다른 산 사슴
  줄 수(0 이어야)·모든 결정과 길 결정의 1·2위 로짓 차 최솟값·근접 동점(< 1e-4) 수, chain = 칸마다 스텝 sha256 32 바이트를 이은 것의 sha256,
  events.decide = [s, 슬롯, 시작, SHELTER 가능(마스크 칸 4), k*, 요청, 고른 길(RUN 0·SHELTER 2 — 다음 스텝 첫머리에 적용)], events.death = [s, 슬롯, 까닭],
  route_off (route0 만) = 길 끈 같은 일(관측 21) + obs21zero 기록과 같은가 (계획서 10-2 받아들일 조건 1 의 파이썬 쪽 — flight.route 칸만 뺀다).
MANIFEST.json: 만든 커밋·명령·세계·두뇌·판마다 파일 sha256·요약, 신선도 입력(world.py·rep_policy.py·export_weights_v3.py 등) sha256.
결정성: 시각·절대 경로를 적지 않는다(커밋은 MANIFEST 의 commit 칸에만). 같은 코드·설정·두뇌면 바이트 단위로 같다(tests/test_route_port_v3.py —
빠른 시험은 짧은 앞부분, 전부는 느린 시험).
"""

from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
PORT = HERE.parent
ROOT = HERE.parents[4]                              # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "live", ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
           ROOT / "results" / "v3" / "wild2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import numpy as np  # noqa: E402

SNAPSHOT = ROOT / "results" / "v3" / "live" / "pilot" / "eco_v3_snapshot_s20004_t475_e1.json"
WORLD_SET = {"features.wild_flight.route": True}
WORLDS = ("N", "G")
REGIONS = ("Barren", "Forest", "Highland")
SEEDS = (34900, 34901)
STEPS = 1800
ROUTE0_SRC = ROOT / "results" / "v3" / "route" / "brains" / "v3_r1_g995_s3_obs24route0.json"
ROUTE0_ZIP = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
OFF_ZIP = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"          # 길 끈 관측 21 두뇌 (route0 의 배포 결정 = 이 두뇌 — route_extend 확인 1)
BRAIN_DIR, TRAJ_DIR, STATS_DIR = PORT / "brains", PORT / "traj", PORT / "stats"
MANIFEST = PORT / "MANIFEST.json"
ROUTE0, SHELTER2 = "v3_r1_g995_s3_obs24route0", "v3_obs24route_shelter2"
BRAINS = (ROUTE0, SHELTER2)
SHELTER_LABEL = ("늘 SHELTER 시험 두뇌 — route0 + 출력층 칸 4 편향 = 칸 1 + 2 (길 결정에서 SHELTER 가 열리면 늘 SHELTER). C++ 이식 대조 전용, 학습·판정에 "
                 "쓰지 않는다 (results/v3/route/port/make_traces.py)")
GROUPS = ("clock", "deer", "fate", "beh", "obs", "req", "kin", "wolf", "route")
VEC_KEYS = ("to_centroid", "separation", "away_from_pred", "food_grad")   # = ceval.VEC_KEYS
HEX = 8
NEAR_TIE = 1e-4
FORMAT, VERSION = "eco_v3_route_port", 1
JUDGE = (37000, 37200)                              # R6 판정·고르기·점검 시드 (설계 16-9) — 쓰지 않는다
# 신선도 입력 (MANIFEST.inputs — 시험이 지금 파일과 견준다). 늘 SHELTER 두뇌를 만드는 export_golden_v3_route.brain_model 은 두뇌 파일 sha256 이 덮는다.
INPUTS = ("env_v2/world.py", "env_v2/rep_policy.py", "env_v2/features.py", "env_v2/rollout.py", "export_weights_v3.py",
          "configs/v3_wild3_obs_mirror.yaml", "configs/v3_wild3_route_mirror.yaml", "results/v3/adapt/adapt.py",
          "results/v3/live/pilot/eco_v3_snapshot_s20004_t475_e1.json", "results/v3/route/brains/v3_r1_g995_s3_obs24route0.json")


def _rel(p: Path) -> str:
    return Path(p).resolve().relative_to(ROOT).as_posix()


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_name(brain: str, world: str, region: str, seed: int) -> str:
    return f"{brain}__{world}__{region}__{int(seed)}"


def all_runs() -> list[tuple]:
    return [(b, wd, r, s) for b in BRAINS for wd in WORLDS for r in REGIONS for s in SEEDS]


def brain_json(brain: str, folder: Path = BRAIN_DIR) -> Path:
    return Path(folder) / f"{brain}.json"


def brain_zip(brain: str, folder: Path = BRAIN_DIR) -> Path:
    return ROUTE0_ZIP if brain == ROUTE0 else Path(folder) / f"{brain}.zip"


def brain_weights(path: Path) -> dict:
    """두뇌 파일 → export_weights_v3.forward_np 가 받는 가중치 dict (W0·B0·W1·B1·W2·B2 float32)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    W = {}
    for L in d["layers"]:
        W[L["weight"]] = np.frombuffer(base64.b64decode(L["w_f32le_b64"]), dtype="<f4").reshape(L["out"], L["in"])
        W[L["bias"]] = np.frombuffer(base64.b64decode(L["b_f32le_b64"]), dtype="<f4")
    return W


def clean(x):
    """JSON 에 넣을 수 있게: numpy 수 → 파이썬 수, NaN → null, ±∞ → ±1e300."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return clean(x.tolist())
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        if v != v:
            return None
        return v if abs(v) != float("inf") else (1e300 if v > 0 else -1e300)
    return x


def dumps(d: dict) -> str:
    """결정적인 JSON (키 차례 그대로, 맨 위 칸마다 한 줄)."""
    parts = ["{"]
    items = list(d.items())
    for j, (k, v) in enumerate(items):
        sep = "," if j + 1 < len(items) else ""
        parts.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, separators=(',', ':'), allow_nan=False)}{sep}")
    parts.append("}")
    return "\n".join(parts) + "\n"


def gz(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0)


# --------------------------------------------------------------------- #
# 두뇌 파일
# --------------------------------------------------------------------- #


def _route_golden():
    import export_golden_v3_route as eg

    return eg


def make_shelter_zip(out_zip: Path) -> str:
    """늘 SHELTER 시험 두뇌 모델 zip (route0 zip + 칸 4 편향 = 칸 1 + 2). SB3 save 뒤 zip 항목 시각·data 를 고정해 다시 쓴다(zero_extend — 같은 바이트)."""
    import importlib.util

    import torch as th

    eg = _route_golden()
    spec = importlib.util.spec_from_file_location("_zero_extend_for_port", ROOT / "results" / "v3" / "r5" / "zero_extend.py")
    zx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(zx)
    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        m = eg.brain_model(eg.SHELTER_DELTA)
        m._last_obs = None
        m._last_original_obs = None
        m._last_episode_starts = None
        out_zip = Path(out_zip)
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(out_zip))
    finally:
        th.set_num_threads(prev)
    zx._deterministic_zip(out_zip)
    return file_sha256(out_zip)


def make_brains(folder: Path = BRAIN_DIR, log=print) -> dict:
    """brains/ : route0 두뇌 파일 사본 + 늘 SHELTER 시험 두뇌 zip·두뇌 파일. 반환 {이름: 두뇌 파일 dict}."""
    import export_weights_v3 as ew

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if not ROUTE0_ZIP.exists():
        raise SystemExit(f"{ROUTE0_ZIP} 없음 (results/v3/route/route_extend.py 가 만든다)")
    r0 = json.loads(ROUTE0_SRC.read_text(encoding="utf-8"))
    if file_sha256(ROUTE0_ZIP) != r0["model"]["sha256"]:
        raise SystemExit("route0 모델 zip 이 두뇌 파일의 모델 sha256 과 다르다")
    brain_json(ROUTE0, folder).write_bytes(ROUTE0_SRC.read_bytes())
    log(f"  {ROUTE0}.json (results/v3/route/brains 사본)")
    zsha = make_shelter_zip(brain_zip(SHELTER2, folder))
    d = ew.export_brain_file(brain_zip(SHELTER2, folder), brain_json(SHELTER2, folder), world_label=SHELTER_LABEL)
    d["model"]["path"] = f"{_rel(BRAIN_DIR)}/{SHELTER2}.zip"          # 올리는 자리 (임시 폴더에서 만들어도 같은 바이트 — ceval 이 ROOT/model.path 로 찾는다)
    ew.write_brain_file(brain_json(SHELTER2, folder), d)
    log(f"  {SHELTER2}.zip (sha256 {zsha[:12]}) · .json ({d['id']}, 관측 {d['obs_dim']}·판 {d['mask_version']}·계약 {d['contract_hash']}·골든 {d['golden']['count']})")
    out = {ROUTE0: r0, SHELTER2: d}
    if d["contract_hash"] != r0["contract_hash"] or d["mask_version"] != 4 or d["obs_dim"] != 24:
        raise SystemExit("늘 SHELTER 시험 두뇌의 계약이 route0 과 다르다")
    return out


# --------------------------------------------------------------------- #
# 일 (ceval compare --world-set features.wild_flight.route=true 와 같은 길)
# --------------------------------------------------------------------- #


def make_jobs(steps: int = STEPS) -> dict:
    """{(세계, 지역, 시드): job}. 스냅숏 → live.prepare(임시 폴더) → ceval.eval_items(…, world_set=WORLD_SET). job['model'] 은 route0 zip."""
    import ceval
    import live

    snap = live.read_snapshot(SNAPSHOT)
    with tempfile.TemporaryDirectory(prefix="eco_route_port_") as td:
        info = live.prepare(SNAPSHOT, snap, Path(td) / "prep", live.brain_folders(live.DEFAULT_ROOT))
        jobs = {}
        for wd in WORLDS:
            for _, _, job in ceval.eval_items(info, "port", ROUTE0_ZIP, SEEDS, int(steps), wd, world_set=WORLD_SET):
                jobs[(wd, job["region"], int(job["seed"]))] = job
    if sorted(jobs) != sorted((wd, r, s) for wd in WORLDS for r in REGIONS for s in SEEDS):
        raise SystemExit(f"일 목록이 세계 × 지역 × 시드와 다르다: {sorted(jobs)}")
    return jobs


def job_digest(job: dict) -> str:
    """일의 세계 설정·먹이 지도 지문 (sha1 앞 12 자리 — 모델 경로·시드는 빼고)."""
    d = dict(cfg=job["cfg"], snap_food=job.get("snap_food"), region=job["region"])
    return hashlib.sha1(json.dumps(clean(d), sort_keys=True).encode()).hexdigest()[:12]


# --------------------------------------------------------------------- #
# 궤적 지문
# --------------------------------------------------------------------- #


def trace_state(w, req) -> dict:
    """ceval.python_trace 의 한 줄과 같은 칸 (numpy 그대로) + 계획서 7-3 의 길 칸."""
    from env_v2.world import WF_PANIC

    req = np.asarray(req).reshape(-1).astype(np.int64)
    live = np.asarray(w.death_cause) == 0
    rd = np.asarray(w.route_decide, dtype=bool)
    return dict(t=int(w.t), dark=float(w.dark), pred_ema=float(w.pred_ema), x=w.pos[:, 0], y=w.pos[:, 1], hx=w.head[:, 0], hy=w.head[:, 1],
                energy=w.energy, reserve=(w.reserve if w._wr is not None else np.zeros(w.N)), behavior=w._rs.behavior, request=req,
                keep=np.asarray(w.wf_mode), cause=w.death_cause, obs=w._obs, **{k: w._g[k] for k in VEC_KEYS},
                wolves=dict(x=w.pred_pos[:, 0], y=w.pred_pos[:, 1], hx=w.pred_head[:, 0], hy=w.pred_head[:, 1], cd=w.pred_cd,
                            sat=np.asarray(getattr(w, "pred_sat", np.zeros(w.M))), asleep=np.asarray(w.pred_asleep),
                            target=np.asarray(getattr(w, "pred_target", np.full(w.M, -1)))),
                route=w.flight_route, route_k=w.route_k, route_age=w.route_age, route_feas=w.route_feas, route_decide=rd,
                route_req=np.where(rd & (np.asarray(w.wf_mode) == WF_PANIC) & live, req, -1))


def digest_state(st: dict, alive0, first: bool = False) -> dict:
    """한 스텝 상태(trace_state 또는 같은 칸의 C++ trace dict — 목록도 된다) → {칸: sha256 32 바이트}. 모듈 docstring '궤적 지문'."""

    def b(x, dt, sel=None):
        a = np.asarray(x, dtype=dt)
        if sel is not None:
            a = a[sel]
        return np.ascontiguousarray(a).tobytes()

    def h(*parts):
        return hashlib.sha256(b"".join(parts)).digest()

    alive0 = np.asarray(alive0, dtype=bool)
    cause = np.asarray(st["cause"], dtype=np.int64)
    keep = np.asarray(st["keep"], dtype=np.int64)
    live = cause == 0
    keep_ok = live & (keep < 2)
    wv = st["wolves"]
    tgt = np.full(len(np.asarray(wv["x"])), -1) if first else wv["target"]
    return dict(
        clock=h(b([st["t"]], "<i8"), b([st["dark"]], "<f8"), b([st["pred_ema"]], "<f8")),
        deer=h(*(b(st[k], "<f8") for k in ("x", "y", "hx", "hy", "energy", "reserve"))),
        fate=h(b(keep, "<i4"), b(cause, "<i4")),
        beh=h(b(st["behavior"], "<i4", alive0)),
        obs=h(b(st["obs"], "<f4", alive0)),
        req=h(b(st["request"], "<i4", keep_ok)),
        kin=h(*(b(st[k], "<f8", alive0) for k in VEC_KEYS)),
        wolf=h(*(b(wv[k], "<f8") for k in ("x", "y", "hx", "hy")), *(b(wv[k], "<i4") for k in ("cd", "sat", "asleep")), b(tgt, "<i4")),
        route=h(*(b(st[k], "<i4", live) for k in ("route", "route_k", "route_age", "route_feas", "route_decide", "route_req"))),
    )


def trace_run(job: dict, brain: str, steps: int, folder: Path = BRAIN_DIR) -> dict:
    """한 판의 궤적 지문·사건·두뇌 확인 (ceval.python_trace 와 같은 세계·정책 — rep_learned argmax)."""
    import ceval
    import export_weights_v3 as ew
    from env_v2 import rollout as ro
    from env_v2.repertoire import SLEEP
    from env_v2.world import ROUTE_RUN, ROUTE_SHELTER, WF_PANIC

    w = ceval.make_world(job)
    if w.alive is None or not w._route_brain or w.obs_dim != 24:
        raise ValueError("판 단위 대조는 부활 없는 두 길 세계(관측 24)만")
    w.track_flight = True
    pol = ro.build_policy({"kind": "rep_learned", "path": str(brain_zip(brain, folder))}, int(job["seed"]))
    ro.forward_bind(pol, w)
    W = brain_weights(brain_json(brain, folder))
    chk = dict(argmax_mismatch=0, decisions=0, route_decisions=0, near_ties=0, min_top_gap=float("inf"), min_route_gap=float("inf"))
    ev_dec, ev_death, lines = [], [], []
    chain = {g: hashlib.sha256() for g in GROUPS}

    def act():
        obs = w.observe()
        a = np.asarray(pol(obs), dtype=np.float64)
        m = pol.last_mask
        live = np.asarray(w.death_cause) == 0
        lg = ew.forward_np(obs, W, np.float32)
        ai = a[:, 0].astype(np.int64)
        chk["argmax_mismatch"] += int(np.count_nonzero((ew.masked_argmax(lg, m) != ai) & live))
        gp = ew.top_gap(lg, m)
        multi = live & (m.sum(1) >= 2)
        rd = live & np.asarray(w.route_decide, dtype=bool) & (np.asarray(w.wf_mode) == WF_PANIC)
        if multi.any():
            chk["min_top_gap"] = min(chk["min_top_gap"], float(gp[multi].min()))
            chk["decisions"] += int(multi.sum())
            chk["near_ties"] += int(np.count_nonzero(gp[multi] < NEAR_TIE))
        if (rd & multi).any():
            chk["min_route_gap"] = min(chk["min_route_gap"], float(gp[rd & multi].min()))
            chk["route_decisions"] += int((rd & multi).sum())
        for i in np.flatnonzero(rd):
            i = int(i)
            sok = bool(m[i, SLEEP])
            ev_dec.append([int(w.t), i, int(bool(w.route_onset[i])), int(sok), int(w.route_cand_k[i]), int(ai[i]),
                           ROUTE_SHELTER if (ai[i] == SLEEP and sok) else ROUTE_RUN])
        return a

    def record(s, alive0):
        dg = digest_state(trace_state(w, a), alive0, first=s == 0)
        lines.append(json.dumps([s] + [dg[g].hex()[:HEX] for g in GROUPS], separators=(",", ":")))
        for g in GROUPS:
            chain[g].update(dg[g])

    a = act()
    record(0, np.ones(w.N, dtype=bool))
    for s in range(1, int(steps) + 1):
        alive0 = np.asarray(w.death_cause) == 0
        w.step(a)
        for i in np.flatnonzero(alive0 & (np.asarray(w.death_cause) != 0)):
            ev_death.append([s, int(i), int(w.death_cause[i])])
        a = act()
        record(s, alive0)
    cause = np.asarray(w.death_cause)
    fl = w.flight_stats()
    return dict(lines=lines, chain={g: chain[g].hexdigest() for g in GROUPS}, events=dict(decide=ev_dec, death=ev_death), check=clean(chk),
                end=clean(dict(caught=int((cause == 1).sum()), starved=int((cause == 2).sum()), alive=int((cause == 0).sum()), flight=fl,
                               repertoire=w.repertoire_stats())), n=int(w.N), m=int(w.M))


# --------------------------------------------------------------------- #
# 세계 기록
# --------------------------------------------------------------------- #


def record_run(job: dict, model: Path) -> dict:
    """ceval compare 파이썬 쪽 기록 (adapt._world_one = r4_eval._one 칸, 스냅숏 먹이 지도) — wall_s 는 뺀다(시각)."""
    import adapt as ad

    j = copy.deepcopy(job)
    j["model"] = str(model)
    r = ad._world_one(j)
    r.pop("wall_s", None)
    return clean(r)


def off_job(job: dict) -> dict:
    """같은 일의 길 끈 세계 (관측 21 — obs21zero 두뇌)."""
    j = copy.deepcopy(job)
    j["cfg"]["v2"]["features"]["wild_flight"]["route"] = False
    j["model"] = str(OFF_ZIP)
    return j


def compare_off(rec: dict, off: dict) -> dict:
    """route0 기록 = 길 끈 obs21zero 기록인가 (flight.route 칸만 뺀다 — 길 끈 세계에는 없다)."""
    diff = []
    for k in sorted(set(rec) | set(off)):
        a, b = rec.get(k), off.get(k)
        if k == "flight" and isinstance(a, dict) and isinstance(b, dict):
            a = {kk: v for kk, v in a.items() if kk != "route"}
        if a != b:
            diff.append(k)
    return dict(same=not diff, differ=diff)


def _work(args) -> tuple:
    kind, brain, wd, region, seed, steps, job, folder = args
    import torch

    torch.set_num_threads(1)
    if kind == "trace":
        return kind, run_name(brain, wd, region, seed), trace_run(job, brain, steps, Path(folder))
    if kind == "record":
        return kind, run_name(brain, wd, region, seed), record_run(job, brain_zip(brain, Path(folder)))
    if kind == "off":
        return kind, run_name(brain, wd, region, seed), record_run(off_job(job), OFF_ZIP)
    raise ValueError(kind)


# --------------------------------------------------------------------- #
# 조립
# --------------------------------------------------------------------- #


def traj_text(brain, wd, region, seed, steps, tr) -> str:
    head = dict(format=f"{FORMAT}_traj", version=VERSION, brain=brain, world=wd, region=region, seed=int(seed), steps=int(steps), n=tr["n"], m=tr["m"],
                groups=list(GROUPS), hex=HEX, line="[s, 칸마다 sha256 앞 8 자리] — make_traces.py digest_state")
    return json.dumps(head, ensure_ascii=False, separators=(",", ":")) + "\n" + "\n".join(tr["lines"]) + "\n"


def stats_doc(brain, wd, region, seed, steps, job, tr, rec, off) -> dict:
    same = all(tr["end"][k] == rec[k] for k in ("caught", "starved", "alive")) and tr["end"]["flight"] == rec.get("flight")
    if not same:
        raise SystemExit(f"{run_name(brain, wd, region, seed)}: 궤적 판 끝과 기록 판이 다르다 (같은 세계·같은 두뇌여야 한다)")
    rt = rec["flight"]["route"]
    h = rec["flight"]["hide"]
    d = dict(format=f"{FORMAT}_stats", version=VERSION, brain=brain, world=wd, region=region, seed=int(seed), steps=int(steps), n=tr["n"], m=tr["m"],
             job=dict(snapshot=_rel(SNAPSHOT), world_set=WORLD_SET, nosat=wd == "N", digest=job_digest(job)),
             summary=dict(caught=rec["caught"], starved=rec["starved"], alive=rec["alive"], started=rec["flight"]["started"], chased=h["chased"],
                          hidden=h["hidden"], cover_then_caught=h["cover_then_caught"], decisions=rt["decisions"], choice=rt["choice"],
                          picked_run=rt["picked"]["run"], picked_shelter=rt["picked"]["shelter"], invalid_shelter=rt["invalid"]["shelter"],
                          switches=rt["switches"], steps_run=rt["steps"]["run"], steps_shelter=rt["steps"]["shelter"],
                          decide_frac=tr["end"]["repertoire"].get("decide_frac")),
             check=tr["check"], record=rec, trace=dict(record_same=True, repertoire=tr["end"]["repertoire"]), chain=tr["chain"], events=tr["events"])
    if off is not None:
        d["route_off"] = dict(compare_off(rec, off), brain="ckpt/v3/v3_r1_g995_s3_obs21zero.zip", world="같은 일 + features.wild_flight.route false")
    return d


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def manifest_doc(files: dict, brains: dict, jobs: dict, steps: int, workers: int) -> dict:
    runs = []
    for b, wd, r, s in all_runs():
        nm = run_name(b, wd, r, s)
        tk, sk = f"traj/{nm}.jsonl.gz", f"stats/{nm}.json"
        if tk not in files:
            continue
        st = json.loads(files[sk])
        runs.append(dict(run=nm, traj=tk, traj_sha256=hashlib.sha256(files[tk]).hexdigest(), stats=sk,
                         stats_sha256=hashlib.sha256(files[sk]).hexdigest(), summary=st["summary"], check=st["check"],
                         route_off_same=st.get("route_off", {}).get("same")))
    bd = {}
    for nm, d in brains.items():
        bd[nm] = dict(json=f"brains/{nm}.json", json_sha256=hashlib.sha256(files[f"brains/{nm}.json"]).hexdigest(), id=d["id"],
                      weights_sha256=d["weights_sha256"], contract_hash=d["contract_hash"], obs_dim=d["obs_dim"], mask_version=d["mask_version"],
                      model=d["model"], rule=("route0 (results/v3/route/route_extend.py — obs21zero + 길 관측 세 열 0 + 칸 4 = 칸 1 − 2), 배포 결정 늘 RUN"
                                              if nm == ROUTE0 else SHELTER_LABEL))
    return dict(
        format=f"{FORMAT}_manifest", version=VERSION, plan="AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-2",
        made_by="herbivore_rl/results/v3/route/port/make_traces.py", commit=git_head(),
        command=f"python results/v3/route/port/make_traces.py --workers {int(workers)}",
        compare=("python results/v3/live/ceval.py compare --snapshot results/v3/live/pilot/eco_v3_snapshot_s20004_t475_e1.json "
                 "--world-set features.wild_flight.route=true --brain results/v3/route/port/brains/<두뇌>.json --seeds 34900-34901 --horizon 1800 "
                 "--worlds N G --trace 1800   (평가기가 길 세계를 받은 뒤 — 계획서 7절)"),
        world=dict(snapshot=_rel(SNAPSHOT), snapshot_sha256=file_sha256(SNAPSHOT), world_set=WORLD_SET,
                   worlds=dict(G="스냅숏 판정 세계(live.prepare world.yaml — 관측 21 거울 바탕) + 세계 덮기 — 늑대 포만 게임 값",
                               N="G + wild_satiation.enabled false"),
                   regions=list(REGIONS), seeds=list(SEEDS), steps=int(steps), n=128, m=4,
                   job_digests={f"{wd}__{r}__{s}": job_digest(jobs[(wd, r, s)]) for wd, r, s in sorted(jobs)}),
        brains=bd,
        traj=dict(groups=list(GROUPS), hex=HEX, steps="s = 0..T (0 = reset 직후) — ceval.python_trace 줄과 같은 자리",
                  chain="stats 의 chain = 칸마다 스텝 sha256 32 바이트를 이은 것의 sha256"),
        inputs={p: file_sha256(ROOT / p) for p in INPUTS},
        files={k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())},
        runs=runs)


def build(steps: int = STEPS, workers: int = 4, only=None, brains_folder: Path | None = None, log=print) -> dict:
    """{port 기준 상대 경로 → 바이트}. only = 판 이름 목록(없으면 전부 — 그때만 brains·MANIFEST 도). brains_folder = 두뇌를 둘 곳(None 이면 임시 폴더에
    새로 만들고 결과의 brains/ 에 넣는다 — 올린 두뇌와 같은 바이트여야 한다)."""
    names = [run_name(*r) for r in all_runs()]
    if only is not None and set(only) - set(names):
        raise SystemExit(f"없는 판 이름: {sorted(set(only) - set(names))}")
    for s in SEEDS:
        if JUDGE[0] <= s < JUDGE[1]:
            raise SystemExit(f"시드 {s} 는 R6 판정·고르기·점검 범위다")
    with tempfile.TemporaryDirectory(prefix="eco_route_port_brains_") as td:
        folder = Path(brains_folder) if brains_folder is not None else Path(td)
        if brains_folder is None:
            log("두뇌:")
            brains = make_brains(folder, log)
        else:
            brains = {b: json.loads(brain_json(b, folder).read_text(encoding="utf-8")) for b in BRAINS}
        log("일 (스냅숏 → live.prepare → ceval.eval_items, 세계 덮기 route=true):")
        jobs = make_jobs(steps)
        runs = [r for r in all_runs() if only is None or run_name(*r) in only]
        args = []
        for b, wd, r, s in runs:
            job = jobs[(wd, r, s)]
            args.append(("trace", b, wd, r, s, steps, job, str(folder)))
            args.append(("record", b, wd, r, s, steps, job, str(folder)))
            if b == ROUTE0:
                args.append(("off", b, wd, r, s, steps, job, str(folder)))
        log(f"돌리기: 판 {len(runs)} × (궤적·기록) + route0 길 끈 기록 {sum(1 for x in args if x[0] == 'off')} = 일 {len(args)}, 프로세스 {workers}")
        res: dict = {}
        if workers <= 1:
            for x in args:
                k, nm, v = _work(x)
                res[(k, nm)] = v
                log(f"  {k:<6} {nm}")
        else:
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(max_workers=min(int(workers), len(args))) as ex:
                for k, nm, v in ex.map(_work, args):
                    res[(k, nm)] = v
                    log(f"  {k:<6} {nm}")
        files: dict = {}
        for b, wd, r, s in runs:
            nm = run_name(b, wd, r, s)
            tr, rec, off = res[("trace", nm)], res[("record", nm)], res.get(("off", nm))
            files[f"traj/{nm}.jsonl.gz"] = gz(traj_text(b, wd, r, s, steps, tr))
            files[f"stats/{nm}.json"] = dumps(stats_doc(b, wd, r, s, steps, jobs[(wd, r, s)], tr, rec, off)).encode("utf-8")
        if only is None:
            for b in BRAINS:
                files[f"brains/{b}.json"] = brain_json(b, folder).read_bytes()
            files[f"brains/{SHELTER2}.zip"] = brain_zip(SHELTER2, folder).read_bytes()
            files["MANIFEST.json"] = dumps(manifest_doc(files, brains, jobs, steps, workers)).encode("utf-8")
    return files


def read_traj(path_or_bytes) -> tuple[dict, list]:
    """traj 파일 → (머리 dict, [[s, 칸 16 진…], …])."""
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    rows = gzip.decompress(data).decode("utf-8").splitlines()
    return json.loads(rows[0]), [json.loads(x) for x in rows[1:]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=PORT)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", default=None, help="판 이름 (예: v3_obs24route_shelter2__N__Forest__34900) — 두뇌는 올린 brains/ 를 쓴다")
    ap.add_argument("--check", action="store_true", help="올린 파일과 바이트까지 같은지만 본다 (MANIFEST 의 commit 칸은 빼고)")
    a = ap.parse_args(argv)
    out = a.out if a.out.is_absolute() else Path.cwd() / a.out
    files = build(a.steps, a.workers, a.only, brains_folder=BRAIN_DIR if a.only is not None else None)
    if a.check:
        bad = []
        for k, v in files.items():
            p = out / k
            if not p.exists():
                bad.append(k)
            elif k == "MANIFEST.json":
                x, y = json.loads(p.read_text(encoding="utf-8")), json.loads(v)
                x.pop("commit", None)
                y.pop("commit", None)
                bad += [k] if x != y else []
            elif p.read_bytes() != v:
                bad.append(k)
        print("최신이다" if not bad else f"다르다: {bad}")
        return 1 if bad else 0
    for k, v in files.items():
        p = out / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(v)
    tot = sum(len(v) for v in files.values())
    print(f"썼다: {out} — 파일 {len(files)} 개, {tot} 바이트")
    if "MANIFEST.json" in files:
        for r in json.loads(files["MANIFEST.json"])["runs"]:
            s, c = r["summary"], r["check"]
            print(f"  {r['run']:<44} 잡힘 {s['caught']:>3} 굶음 {s['starved']:>2} 길 결정 {s['decisions']:>4} (두 칸 {s['choice']:>3}, SHELTER {s['picked_shelter']:>3}) "
                  f"숨음 {s['hidden']:>3}/{s['chased']:>3} · argmax 차 {c['argmax_mismatch']} 최소 로짓 차 {c['min_top_gap']:.4g} 근접 동점 {c['near_ties']}"
                  + ("" if r["route_off_same"] is None else f" · 길 끈 obs21zero 와 같음 {r['route_off_same']}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
