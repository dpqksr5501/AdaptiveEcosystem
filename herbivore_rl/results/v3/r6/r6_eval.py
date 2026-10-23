"""v3 R6 (두 길 두뇌) 점검·고르기·판정 도구 — 사전 등록 results/v3/r6/PREREG.md 4~7절 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16-8·16-9).

판정 실행기는 파이썬이다(두 길은 아직 C++ 평가기에 없다 — 16-8). 세계 = 스냅숏 eco_v3_snapshot_s20004_t475_e1.json 의 G(게임 그대로)·N(G + 늑대 포만 끔)
(실시간 고리 변환 live.prepare — 도망길 측정 m1·단서 측정 cues1 과 같은 세계, 먹이 지도 = 스냅숏). 세계 하나 = live._world_multi(run_mirror.run_world)
그대로이고, 두뇌의 관측 칸 수로 길 키를 정한다: 관측 24(R6·route0) = wild_flight.route 켬, 관측 21(대조 '길 끔'·obs21zero) = 끔, 'shelter_rule'
= obs21zero + wild_flight.route_fixed shelter(손 규칙 '늘 SHELTER' — 보고만, 측정 전용 옛 규칙 그대로 — 설계 16-3).

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/r6/r6_eval.py run --use check  --model route0 --probe --name early_base            # 조기 점검 기준 판 (37120~37139)
    python results/v3/r6/r6_eval.py run --use check  --model ckpt/v3/<점검 모델>.zip --probe --flight-cost 0.0027 --name early_<꼬리>
    python results/v3/r6/r6_eval.py check --run results/v3/r6/runs/early_<꼬리>.json --base results/v3/r6/runs/early_base.json --lam 0.95
    python results/v3/r6/r6_eval.py select --models ckpt/v3/v3_r6_g995_s0_20m.zip ckpt/v3/v3_r6_g995_s1_20m.zip ckpt/v3/v3_r6_g995_s2_20m.zip
    python results/v3/r6/r6_eval.py judge --model ckpt/v3/v3_r6_g995_s<고른 시드>_20m.zip --off ckpt/v3/v3_r6off_g995_s0_20m.zip
    python results/v3/r6/r6_eval.py run --use smoke --model route0 --probe --seeds 32080-32081 --steps 300 --name smoke_route0    # 도구 확인

쓰임(--use)이 시드·길이·세계를 정한다(사전 등록 2절 — 다른 쓰임의 시드를 쓸 수 없다):
  check   조기 점검   37120~37139 × 지역 셋, N, 1800 스텝
  select  모델 고르기 37100~37119 × 지역 셋, N, 1800 스텝
  judge_n 판정 N      37000~37099 × 지역 셋, N, 1800 스텝 (P1·GH·GN·GF·GV·GC·GT·GTr·GR·G4 N, 보고 줄)
  judge_g 판정 G      37000~37039 × 지역 셋, G, 3600 스텝 (GG·G4 G·G6)
  stuck   끼임 G5     37000~37004 × 지역 셋, G, 3600 스텝
  smoke   도구 확인   32080~32099 안(--seeds·--steps 를 준다), N — R6 시드 37000~37199 는 받지 않는다
--probe(조기 점검): 같은 세계를 같은 두뇌로 돌리면서(세계·궤적은 그대로 — 시험 tests/test_r6_prereg.py) 길 결정의 SHELTER 확률과 도주 스텝의 가치망 설명
분산을 함께 잰다(_Probe — 수익 목표 λ 0.95·0.98·1 셋, (b) 는 점검 모델의 학습 λ 칸 · check --lam). --flight-cost 는 설명 분산의 보상에만 쓴다
(그 학습 세계의 도주 비용 — 보상 전용 키라 세계는 그대로다).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
           ROOT / "results" / "v3" / "wild2", ROOT / "results" / "v3" / "live", HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import adapt as ad  # noqa: E402
import live as lv  # noqa: E402
import r4_eval as re_  # noqa: E402

SNAPSHOT = ROOT / "results" / "v3" / "live" / "pilot" / "eco_v3_snapshot_s20004_t475_e1.json"
OUT = HERE.parent / "runs"                          # git 밖 (herbivore_rl/.gitignore runs/)
CK = ROOT / "ckpt" / "v3"
ROUTE0 = CK / "v3_r1_g995_s3_obs24route0.zip"       # 시작 두뇌 route0 (results/v3/route/route_extend.py — 배포 결정 = R1b-F, 길은 늘 RUN)
OBS21ZERO = CK / "v3_r1_g995_s3_obs21zero.zip"      # R1b-F + 장애물 관측 열 0 (대조 '길 끔'의 시작 두뇌, '늘 SHELTER' 규칙의 도주 밖 두뇌)
BRAINS = HERE.parent / "brains"
CONTRACT_ROUTE = "0xe302dee198197444"               # 관측 24·마스크 판 4 계약 해시 (설계 16-5)
GAMMA = 0.995                                       # 학습 γ (설명 분산의 할인 수익)
# 조기 점검 (b) 의 수익 목표 λ (사전 등록 5-1): 탐침은 셋을 모두 재고, (b) 는 그 조합의 학습 GAE λ(0.95·0.98) 칸을 쓴다. 1.0 = 몬테카를로 수익(보고만).
EV_LAMS = (0.95, 0.98, 1.0)
STEP_S = lv.STEP_S
REGIONS = ("Barren", "Forest", "Highland")

# 쓰임 → (시드 처음, 끝, 길이, 세계) — 사전 등록 2절 (설계 16-9 표)
USES = {
    "judge_n": (37000, 37099, 1800, "N"),
    "judge_g": (37000, 37039, 3600, "G"),
    "stuck": (37000, 37004, 3600, "stuck"),
    "select": (37100, 37119, 1800, "N"),
    "check": (37120, 37139, 1800, "N"),
}
R6_SEEDS = (37000, 37199)                           # R6 사전 등록 시드 칸 — 쓰임 밖에서는 받지 않는다
SMOKE_SEEDS = (32080, 32099)                        # 도구 확인 (탐색 칸 32000~32099 의 스모크 몫 — v3_r6_train.yaml 머리)

# 조기 점검 규칙 (사전 등록 5절 — 설계 16-8 1 을 10-23 숨음 비율 잣대로 맞춘 수)
EARLY = dict(
    pi_move=0.05,          # (a) SHELTER 가 열린 길 결정에서 학습 표본 확률 π′(SHELTER) 평균이 시작(route0) 값에서 이보다 크게 움직임 (|차이| > 0.05)
    ev_min=0.0,            # (b) 도주 스텝(도주 반사 덮기 중인 산 사슴) 가치망 설명 분산 > 0
    t_hide=-2.0,           # (c) 숨음 비율 짝 t > −2 (route0 대비 나빠지지 않음)
    t_caught_ratio=2.0,    # (c) 잡힘 비율(쫓긴 도망 가운데) 짝 t < +2
    t_caught=2.0,          # (c) 잡힌 몫(사슴 가운데) 짝 t < +2
    tol_hide=0.01,         # 고르기: 숨음 비율 짝 차이가 가장 큰 조합과 1 %p 안이면 작은 c → λ 0.95
)


# --------------------------------------------------------------------- #
# 두뇌·세계
# --------------------------------------------------------------------- #

def model_obs_dim(path: Path) -> int:
    """모델 zip 의 정책망 첫 층 입력 칸 수(= 관측 칸 수)."""
    import torch as th

    sd = th.load(io.BytesIO(zipfile.ZipFile(path).read("policy.pth")), map_location="cpu", weights_only=True)
    w = sd.get("mlp_extractor.policy_net.0.weight")
    if w is None:
        raise ValueError(f"{path}: 정책망 첫 층이 없다")
    return int(w.shape[1])


def resolve_model(text: str) -> dict:
    """'route0' · 'obs21zero' · 'shelter_rule' · 모델 zip 경로 → dict(label, path, obs, sets — 두뇌가 쓰는 세계 키)."""
    if text == "shelter_rule":
        return dict(label="shelter_rule", path=OBS21ZERO, obs=21, sets={"wild_flight.route_fixed": "shelter"})
    p = {"route0": ROUTE0, "obs21zero": OBS21ZERO}.get(text)
    if p is None:
        p = Path(text)
        p = p if p.is_absolute() else ROOT / p
    if not p.exists():
        raise SystemExit(f"모델 {p} 이 없다")
    d = model_obs_dim(p)
    if d == 24:
        sets = {"wild_flight.route": True}
    elif d == 21:
        sets = {}
    else:
        raise SystemExit(f"{p}: 관측 {d} 칸 두뇌는 받지 않는다 (R6 = 관측 24, 대조 = 관측 21)")
    return dict(label=text if text in ("route0", "obs21zero") else p.stem, path=p, obs=d, sets=sets)


def use_plan(use: str, seeds=None, steps=None) -> dict:
    """쓰임 → dict(use, seeds, steps, world). smoke 만 --seeds·--steps 를 받고(SMOKE_SEEDS 안), 그 밖의 쓰임은 사전 등록 값만 쓴다."""
    if use == "smoke":
        if not seeds or not steps:
            raise SystemExit("--use smoke 는 --seeds 와 --steps 를 준다")
        lo, hi = SMOKE_SEEDS
        bad = [s for s in seeds if not lo <= int(s) <= hi]
        if bad:
            raise SystemExit(f"스모크 시드 {bad[:5]} 는 {lo}~{hi} 밖이다 (R6 사전 등록 시드 {R6_SEEDS[0]}~{R6_SEEDS[1]} 는 쓰임으로만 쓴다)")
        return dict(use=use, seeds=[int(s) for s in seeds], steps=int(steps), world="N")
    if use not in USES:
        raise SystemExit(f"--use {use} 는 {', '.join(list(USES) + ['smoke'])} 가운데 하나다")
    if seeds or steps:
        raise SystemExit(f"--use {use} 의 시드·길이는 사전 등록 값이다 (--seeds·--steps 는 smoke 만)")
    lo, hi, n, world = USES[use]
    return dict(use=use, seeds=list(range(lo, hi + 1)), steps=int(n), world=world)


def parse_seeds(text: str) -> list[int]:
    """'32080-32082' · '32080,32085' → 시드 목록 (겹치면 멈춘다). 받을 범위는 use_plan 이 본다."""
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if part:
            lo, _, hi = part.partition("-")
            out.extend(range(int(lo), int(hi or lo) + 1))
    if not out or len(set(out)) != len(out):
        raise SystemExit(f"시드 {text!r} 가 비었거나 겹친다")
    return out


def smoke_plan(use: str, seeds, steps: int) -> dict:
    """도구 확인용(판정 아님): 쓰임 use 의 세계(N·G·끼임)를 스모크 시드·길이로. 시드는 SMOKE_SEEDS 안만 받는다."""
    p = use_plan("smoke", seeds, steps)
    p.update(use=f"smoke_{use}", world=USES[use][3])
    return p


def prepare_info(out: Path = OUT, snapshot: Path = SNAPSHOT) -> dict:
    """스냅숏 → <out>/world (live.prepare — world.yaml(G)·regions.json·convert.json). 이미 있으면 다시 읽는다."""
    rd = Path(out) / "world"
    if (rd / "convert.json").exists() and (rd / "regions.json").exists():
        rec = json.loads((rd / "convert.json").read_text(encoding="utf-8"))
        return dict(record=rec, regions=json.loads((rd / "regions.json").read_text(encoding="utf-8")), dir=rd)
    snap = lv.read_snapshot(snapshot)
    return lv.prepare(Path(snapshot), snap, rd, lv.brain_folders(Path(out)))


def make_items(info: dict, spec: dict, plan: dict, probe: bool = False, flight_cost: float = 0.0, tag: str = "x") -> list:
    """(종류, 꼬리표, 세계 job) 목록. N = G + 늑대 포만 끔(live.NOSAT), 두뇌 세계 키(spec sets — 길 켬·고정 길), stuck = 끼임 세기(G)."""
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
            j["probe"] = dict(flight_cost=float(flight_cost), gamma=GAMMA)
    return [("probe" if probe else "multi", f"{tag}:{world}", j) for j in jobs]


# --------------------------------------------------------------------- #
# 탐침 (조기 점검 (a)·(b) — 세계·궤적은 그대로)
# --------------------------------------------------------------------- #

def lam_key(lam: float) -> str:
    """λ → 탐침 칸 이름 ('0.95' · '0.98' · '1')."""
    return f"{float(lam):g}"


def lambda_returns(R: np.ndarray, D: np.ndarray, V: np.ndarray, v_end: np.ndarray, gamma: float, lam: float) -> np.ndarray:
    """GAE λ-수익 (PPO 가 가치망을 맞추는 목표 — stable-baselines3 RolloutBuffer.returns = 이점 + V 와 같은 꼴):
    G^λ_t = r_t + γ (1 − d_t) [(1 − λ) V(s_{t+1}) + λ G^λ_{t+1}], 판 끝 뒤 G^λ_T = V(s_T) = v_end. R·D·V 는 (스텝, 사슴).
    λ = 1 이면 몬테카를로 할인 수익(끝만 V(s_T) 로 잇는다), λ = 0 이면 한 스텝 TD 목표 r_t + γ (1 − d_t) V(s_{t+1})."""
    T = len(R)
    G = np.zeros((T,) + np.shape(v_end))
    nxt_v = nxt_g = np.asarray(v_end, dtype=np.float64)
    for t in range(T - 1, -1, -1):
        G[t] = R[t] + gamma * (~D[t]) * ((1.0 - lam) * nxt_v + lam * nxt_g)
        nxt_v, nxt_g = V[t], G[t]
    return G


class _Probe:
    """rep_learned(RepLearned) 바깥 껍질: 행동은 바탕 그대로 내고(argmax), 스텝마다 (a) 길 결정 가운데 SHELTER 가 열린 행의 π·π′(SHELTER), 배포가 고른 길,
    (b) 산 사슴의 가치 V(s)·도주 반사 덮기 여부, 세계 step 의 보상·죽음을 적는다. 세계 상태·난수를 건드리지 않는다(rep_peek 은 순수 — world.py)."""

    def __init__(self, base, gamma: float):
        self.base, self.gamma = base, float(gamma)
        self.world = None
        self._V, self._F, self._L, self._R, self._D = [], [], [], [], []
        self.acc = dict(dec_n=0, two_n=0, pi_sh=0.0, pe_sh=0.0, pick_sh_two=0, pick_sh=0, cover_max=0.0)

    def __getattr__(self, name):
        # 실행기가 읽는 바탕 칸(allowed·params·last_mask·model 등)은 바탕 그대로 (self.__dict__ 에 없는 이름만 여기로 온다)
        if name == "base":
            raise AttributeError(name)
        return getattr(self.base, name)

    def bind_world(self, w) -> None:
        self.base.bind_world(w)
        self.world = w
        self.route = "in_panic" in w.obs_names
        step = w.step

        def rec_step(a):
            o, r, d, to = step(a)
            self._R.append(np.asarray(r, dtype=np.float64).copy())
            self._D.append(np.asarray(d, dtype=bool).copy())
            return o, r, d, to

        w.step = rec_step                   # 이 세계 하나의 step 만 감싼다(값은 그대로 돌려준다)

    def _values(self, pobs) -> np.ndarray:
        import torch as th

        pol = self.base.model.policy
        obs_t, _ = pol.obs_to_tensor(np.asarray(pobs, dtype=np.float32))
        with th.no_grad():
            return pol.predict_values(obs_t).cpu().numpy().astype(np.float64).reshape(-1)

    def __call__(self, obs):
        from env_v2.rep_policy import policy_obs, rep_distribution
        from env_v2.world import WF_PANIC

        a = self.base(obs)
        w, m = self.world, self.base.last_mask
        live = np.ones(w.N, dtype=bool) if w.alive is None else np.asarray(w.alive, dtype=bool).copy()
        self._L.append(live)
        self._F.append((np.asarray(w.wf_mode) == WF_PANIC) & live)
        self._V.append(self._values(policy_obs(obs, m)))
        if self.route:
            rd = np.asarray(w.rep_peek()["route_decide"], dtype=bool)
            two = rd & m[:, 1] & m[:, 4]
            act = np.asarray(a)[:, 0].astype(np.int64)
            c = self.acc
            c["dec_n"] += int(rd.sum())
            c["pick_sh"] += int(np.count_nonzero(rd & (act == 4)))
            if two.any():
                pi, pe, _ = rep_distribution(self.base.model.policy, policy_obs(np.asarray(obs)[two], m[two]))
                c["two_n"] += int(two.sum())
                c["pi_sh"] += float(pi[:, 4].sum())
                c["pe_sh"] += float(pe[:, 4].sum())
                c["pick_sh_two"] += int(np.count_nonzero(act[two] == 4))
                c["cover_max"] = max(c["cover_max"], float(pi[:, 3].max()), float(pe[:, 3].max()))
        return a

    def result(self) -> dict:
        """도주 스텝(산 사슴 ∧ 덮기 = 도주) 표본의 가치 오차 합 — λ 마다(EV_LAMS) 수익 목표 G^λ(lambda_returns)와 V(s) 의 합·제곱합을 낸다.
        판 여럿을 합쳐 설명 분산 1 − Var(G^λ − V) / Var(G^λ) 를 낸다(probe_pooled)."""
        from env_v2.rep_policy import policy_obs

        w = self.world
        T = len(self._R)
        if T != len(self._V):
            raise RuntimeError(f"탐침 기록 길이가 다르다 (보상 {T}, 가치 {len(self._V)})")
        acc = dict(self.acc, ev={lam_key(x): dict(n=0, g_s=0.0, g_s2=0.0, e_s=0.0, e_s2=0.0) for x in EV_LAMS})
        if T == 0:
            return acc
        alive_T = np.ones(w.N, dtype=bool) if w.alive is None else np.asarray(w.alive, dtype=bool)
        v_end = self._values(policy_obs(w.observe(), self.base.mask())) * alive_T
        V, sel = np.asarray(self._V), np.asarray(self._F) & np.asarray(self._L)
        R, D = np.asarray(self._R), np.asarray(self._D)
        for lam in EV_LAMS:
            G = lambda_returns(R, D, V, v_end, self.gamma, lam)
            g, e = G[sel], (G - V)[sel]
            acc["ev"][lam_key(lam)] = dict(n=int(sel.sum()), g_s=float(g.sum()), g_s2=float((g * g).sum()), e_s=float(e.sum()),
                                           e_s2=float((e * e).sum()))
        return acc


def _probe_world(job: dict) -> dict:
    """탐침 세계 하나: live._world_multi 그대로(같은 세계·궤적·도망 기록) + 'probe' 칸. job['probe'] = {flight_cost, gamma}."""
    from env_v2 import rollout as ro

    pr = job.pop("probe")
    if float(pr.get("flight_cost", 0.0)) > 0.0:
        job["cfg"]["v2"]["features"]["wild_flight"]["flight_cost"] = float(pr["flight_cost"])     # 보상 전용 (설명 분산의 보상이 학습 세계와 같게)
    holder: dict = {}
    orig = ro.build_policy

    def build(spec, seed=0):
        p = _Probe(orig(spec, seed), float(pr.get("gamma", GAMMA)))
        holder["p"] = p
        return p

    ro.build_policy = build
    try:
        out = lv._world_multi(job)
    finally:
        ro.build_policy = orig
    out["probe"] = holder["p"].result()
    return out


def _r6_job(item):
    """워커에서 도는 일 하나: (종류, 꼬리표, 세계 job) → (꼬리표, 결과)."""
    kind, tag, job = item
    if kind == "multi":
        return tag, lv._world_multi(job)
    if kind == "probe":
        return tag, _probe_world(job)
    if kind == "stuck":
        return tag, ad._stuck_one(job)
    raise ValueError(f"모르는 일 {kind}")


def run_items(items: list, workers: int, label: str = "") -> list:
    """워커 풀(env_v2.rollout.make_executor)로 일을 돌린다 → [(꼬리표, 결과)] (items 순서). 50 개마다 진행 줄."""
    from concurrent.futures import as_completed

    from env_v2 import rollout as ro

    import r6_eval as R                       # 워커가 이름으로 불러올 수 있게 (스크립트로 돌 때 __main__ 이 아닌 모듈의 함수)

    fn = R._r6_job
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
    """셈 길 지문: 세계(live.eval_code_tag('python') — 판정 파일 바이트·판정 함수·라이브러리 판)와 이 도구 파일 sha256 앞 16."""
    lv._CODE.pop("python", None)
    return dict(world=lv.eval_code_tag("python"), tool=hashlib.sha256(HERE.read_bytes()).hexdigest()[:16])


def run_model(info: dict, text: str, plan: dict, workers: int, probe: bool = False, flight_cost: float = 0.0, name: str = "") -> dict:
    """한 두뇌 · 한 쓰임 → {meta, worlds} (끼임은 {meta, summary})."""
    import stuck_check

    spec = resolve_model(text)
    items = make_items(info, spec, plan, probe, flight_cost, tag=spec["label"])
    t0 = time.perf_counter()
    rows = run_items(items, workers, name or spec["label"])
    meta = dict(name=name, use=plan["use"], world=plan["world"], seeds=plan["seeds"], steps=plan["steps"], regions=sorted(info["regions"]),
                model=text, model_path=lv.path_text(spec["path"]), model_sha1=hashlib.sha1(Path(spec["path"]).read_bytes()).hexdigest()[:12],
                obs=spec["obs"], sets=spec["sets"], probe=bool(probe), flight_cost=float(flight_cost) if probe else None,
                snapshot=SNAPSHOT.name, code=code_tags(), wall_s=round(time.perf_counter() - t0, 1), workers=int(workers))
    if plan["world"] == "stuck":
        return dict(meta=meta, summary=stuck_check.summarize([r for _, r in rows]))
    return dict(meta=meta, worlds=[r for _, r in rows])


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(res: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lv.atomic_write_json(path, lv.jsonable(res), indent=None)
    return path


# --------------------------------------------------------------------- #
# 조기 점검 (사전 등록 5절)
# --------------------------------------------------------------------- #

def probe_pooled(res: dict) -> dict:
    """판의 탐침 합: 길 결정 수·SHELTER 가 열린 결정 수, π·π′(SHELTER) 평균, 배포가 SHELTER 를 고른 몫, COVER 확률 최댓값,
    도주 스텝 설명 분산 ev = {λ 칸 이름: 1 − Var(G^λ − V)/Var(G^λ)} (EV_LAMS — '1' = 몬테카를로)."""
    keys = ("dec_n", "two_n", "pi_sh", "pe_sh", "pick_sh_two", "pick_sh")
    t = {k: 0.0 for k in keys}
    ev = {lam_key(x): dict(n=0, g_s=0.0, g_s2=0.0, e_s=0.0, e_s2=0.0) for x in EV_LAMS}
    cmax = 0.0
    for w in res["worlds"]:
        p = w.get("probe")
        if p is None:
            raise ValueError(f"세계 (시드 {w.get('seed')}, {w.get('region')}) 에 탐침 칸이 없다 — run --probe 로 돌린다")
        if "ev" not in p:
            raise ValueError(f"세계 (시드 {w.get('seed')}, {w.get('region')}) 의 탐침이 옛 꼴이다(λ 별 설명 분산 없음) — 지금 도구로 다시 돌린다")
        for k in keys:
            t[k] += p[k]
        for lk, s in ev.items():
            for k in s:
                s[k] += p["ev"][lk][k]
        cmax = max(cmax, float(p["cover_max"]))
    two = t["two_n"]

    def _ev(s):
        n = s["n"]
        if not n:
            return float("nan")
        vg = s["g_s2"] / n - (s["g_s"] / n) ** 2
        ve = s["e_s2"] / n - (s["e_s"] / n) ** 2
        return (1.0 - ve / vg) if vg > 0 else float("nan")

    return dict(dec_n=int(t["dec_n"]), two_n=int(two), pi_shelter=t["pi_sh"] / two if two else float("nan"),
                pe_shelter=t["pe_sh"] / two if two else float("nan"), pick_shelter_two=t["pick_sh_two"] / two if two else float("nan"),
                pick_shelter=int(t["pick_sh"]), cover_max=cmax, ev_n=int(ev[lam_key(1.0)]["n"]), ev={lk: _ev(s) for lk, s in ev.items()})


def route_pooled(res: dict) -> dict:
    """길 기록(flight.route — 길 켬 세계만) 합: 도주 시작·결정·두 칸 결정·다시 고름·길 바꿈·무효(SHELTER)·고른 길·마스크 밖 SHELTER, 끝난 뒤 5 초 안 다시 도망."""
    t = dict(onsets=0, decisions=0, choice=0, redecide_feas=0, switches=0, invalid_shelter=0, picked_run=0, picked_shelter=0, bad_shelter=0, refled=0,
             started=0, worlds=0)
    for w in res["worlds"]:
        r = (w.get("flight") or {}).get("route")
        if r is None:
            continue
        t["worlds"] += 1
        for k in ("onsets", "decisions", "redecide_feas", "switches", "refled"):
            t[k] += int(r[k])
        t["choice"] += int(r.get("choice", 0))
        t["bad_shelter"] += int(r.get("bad_shelter", 0))
        t["invalid_shelter"] += int(r["invalid"]["shelter"])
        t["picked_run"] += int(r["picked"]["run"])
        t["picked_shelter"] += int(r["picked"]["shelter"])
        t["started"] += int(w["flight"]["started"])
    s = max(t["started"], 1)
    t.update(shelter_share=lv.ratio(t["picked_shelter"], t["picked_run"] + t["picked_shelter"]), per_flight_decisions=t["decisions"] / s,
             per_flight_redecide=t["redecide_feas"] / s, per_flight_invalid=t["invalid_shelter"] / s, per_flight_switches=t["switches"] / s)
    return t


def _ok_t(q: dict, cond: bool) -> bool:
    return bool(int(q["n"]) >= 2 and math.isfinite(q["se"]) and cond)


def early_check(run: dict, base: dict, lam: float, route: bool | None = None) -> dict:
    """조기 점검 하나 (사전 등록 5절): run = 점검 모델 판, base = route0 판 (같은 점검 시드, 둘 다 --probe). lam = 그 모델의 학습 GAE λ
    ((b) 의 수익 목표). route None 이면 run 의 관측으로 정한다 (관측 24 = 두 길 — (a) 를 본다, 관측 21 = 대조 '길 끔' — (a) 없음).
    (a) |π′(SHELTER) − route0| > 0.05, (b) 도주 스텝 설명 분산(학습 λ 의 λ-수익 목표) > 0, (c) 숨음 비율 짝 t > −2 · 잡힘 비율 짝 t < +2 ·
    잡힌 몫 짝 t < +2, 결함 = 얼기·잠 몫 > 0 또는 COVER 칸 확률 > 0 또는 마스크 밖 SHELTER > 0.
    보고만: 몬테카를로 수익(λ 1)의 설명 분산, R5 점검 규칙 칸(도망·은신처 안·굶음 몫)."""
    if sorted((w["seed"], w["region"]) for w in run["worlds"]) != sorted((w["seed"], w["region"]) for w in base["worlds"]):
        raise ValueError("점검 판과 기준 판의 세계가 다르다")
    lk = lam_key(lam)
    if float(lam) not in EV_LAMS[:-1]:
        raise ValueError(f"(b) 의 λ {lam} 는 학습 λ 후보 {EV_LAMS[:-1]} 가운데 하나다")
    route = (int(run["meta"].get("obs", 24)) == 24) if route is None else bool(route)
    pr, pb = probe_pooled(run), probe_pooled(base)
    E = EARLY
    if route:
        moved = pr["pe_shelter"] - pb["pe_shelter"]
        a_ok = bool(pr["two_n"] > 0 and math.isfinite(moved) and abs(moved) > E["pi_move"])
        a = dict(ok=a_ok, pe=pr["pe_shelter"], pe_start=pb["pe_shelter"], moved=moved, pi=pr["pi_shelter"], two_n=pr["two_n"],
                 rule=f"|π′(SHELTER) − route0| > {E['pi_move']:g} (SHELTER 가 열린 길 결정 {pr['two_n']} 개)")
    else:
        a = dict(ok=None, rule="대조 '길 끔' — 길 결정이 없다 (보지 않는다)")
    ev, mc = pr["ev"][lk], pr["ev"][lam_key(1.0)]
    b = dict(ok=bool(pr["ev_n"] >= 2 and math.isfinite(ev) and ev > E["ev_min"]), ev=ev, ev_start=pb["ev"][lk], lam=float(lam), n=pr["ev_n"],
             ev_mc=mc, ev_mc_start=pb["ev"][lam_key(1.0)],
             rule=f"도주 스텝 가치망 설명 분산(λ {lam:g} λ-수익 목표) > {E['ev_min']:g} (표본 {pr['ev_n']})")
    hide, cr = lv.hide_pair(run, base, "hide"), lv.hide_pair(run, base, "caught")
    gn = re_.paired(re_.per_seed(run, "caught"), re_.per_seed(base, "caught"))
    c_parts = dict(hide=dict(hide, ok=_ok_t(hide, hide["t"] > E["t_hide"])), caught_ratio=dict(cr, ok=_ok_t(cr, cr["t"] < E["t_caught_ratio"])),
                   caught=dict(gn, ok=_ok_t(gn, gn["t"] < E["t_caught"])))
    c = dict(ok=all(v["ok"] for v in c_parts.values()), parts=c_parts,
             rule=f"숨음 비율 짝 t > {E['t_hide']:+g} · 잡힘 비율 짝 t < +{E['t_caught_ratio']:g} · 잡힌 몫 짝 t < +{E['t_caught']:g} (route0 대비)")
    pa, pbp = re_.pooled(run), re_.pooled(base)
    rt = route_pooled(run) if route else None
    defect = dict(freeze_sleep=pa["beh"]["freeze"] + pa["beh"]["sleep"], cover_max=pr["cover_max"], bad_shelter=(rt or {}).get("bad_shelter", 0))
    defect["hit"] = bool(defect["freeze_sleep"] > 0 or defect["cover_max"] > 0 or defect["bad_shelter"] > 0)
    starve_lim = 1.5 * pbp["starved"] if pbp["starved"] > 0 else 0.01
    report = dict(flee=(pa["beh"]["flee"], pbp["beh"]["flee"], pa["beh"]["flee"] < 0.5 * pbp["beh"]["flee"]),
                  shelter=(pa["shelter"], pbp["shelter"], pa["shelter"] > 3.0 * pbp["shelter"]),
                  starved=(pa["starved"], pbp["starved"], pa["starved"] > starve_lim))
    return dict(route=route, a=a, b=b, c=c, defect=defect, passed=bool((a["ok"] is not False) and b["ok"] and c["ok"] and not defect["hit"]),
                probe=pr, probe_base=pb, route_stats=rt, pooled=pa, pooled_base=pbp, report_r5=report,
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
    for k, nm in (("hide", "숨음 비율"), ("caught_ratio", "잡힘 비율"), ("caught", "잡힌 몫")):
        q = c["parts"][k]
        lines.append(f"  (c) {nm} {yn(q['ok'])}: {q['a']:.4f} 대 route0 {q['b']:.4f} (차이 {q['diff']:+.4f}, t {lv.tfmt(q['t'])}, 시드 {q['n']})")
    d = r["defect"]
    lines.append(f"  결함 {'있음' if d['hit'] else '없음'}: 얼기·잠 몫 {d['freeze_sleep']:.4g}, COVER 확률 최대 {d['cover_max']:.3g}, 마스크 밖 SHELTER {d['bad_shelter']}")
    if r["route_stats"]:
        s = r["route_stats"]
        lines.append(f"  길: 결정 {s['decisions']} · SHELTER 고름 {s['picked_shelter']} (몫 {s['shelter_share']:.4f}) · 다시 고름 {s['redecide_feas']} · 무효 {s['invalid_shelter']}")
    rep = r["report_r5"]
    lines.append("  보고만(R5 점검 칸): " + " · ".join(f"{k} {x:.4f} (route0 {y:.4f}{' — R5 규칙이면 걸림' if hit else ''})" for k, (x, y, hit) in rep.items()))
    return "\n".join(lines)


def pick_combo(checks: dict) -> dict:
    """조기 점검 6 조합 고르기 (사전 등록 5-2). checks = {(λ 이름, c 이름): early_check}. 반환 dict(stop, why, pick, near, ranking)."""
    if any(v["defect"]["hit"] for v in checks.values()):
        bad = [f"λ{k[0]}·c{k[1]}" for k, v in checks.items() if v["defect"]["hit"]]
        return dict(stop=True, why=f"결함(얼기·잠·COVER·마스크 밖 SHELTER): {', '.join(bad)} — 고친 뒤 다시 (사람에게 알림)", pick=None)
    passing = [k for k, v in checks.items() if v["passed"]]
    if not passing:
        if not any(v["a"]["ok"] for v in checks.values()):
            why = "모든 조합이 (a) 에서 움직이지 않았다 — '못 배움' 으로 멈추고 보고한다"
        elif any(v["a"]["ok"] and v["c"]["ok"] and not v["b"]["ok"] for v in checks.values()):
            why = "(a)·(c) 를 넘은 조합이 모두 (b) 에서 걸렸다 — 멈추고 관측 25 대안(설계 16-4)을 사람에게 묻는다"
        else:
            why = "(a)~(c) 를 모두 넘은 조합이 없다 — 멈추고 보고한다"
        return dict(stop=True, why=why, pick=None)
    diff = {k: checks[k]["c"]["parts"]["hide"]["diff"] for k in passing}
    best = max(diff.values())
    near = [k for k in passing if diff[k] >= best - EARLY["tol_hide"]]
    from make_r6_configs import COSTS, LAMBDAS

    near.sort(key=lambda k: (COSTS[k[1]], 0 if k[0] == "95" else 1, LAMBDAS[k[0]]))
    rank = sorted(passing, key=lambda k: -diff[k])
    return dict(stop=False, why="", pick=near[0], near=near, best=best, ranking=[(k, diff[k]) for k in rank])


def main_check_rules(checks: dict, at: list[int]) -> dict:
    """본 학습 점검 모음 (사전 등록 5-3). checks = {(시드 이름, k): early_check} (시드 이름 's0'·'s1'·'s2'·'off'). 반환: 시드마다 제외 여부·까닭, 전체 멈춤."""
    seeds = sorted({s for s, _ in checks if s != "off"})
    out: dict = dict(excluded={}, stop=False, why=[], defect=False)
    for s in seeds:
        bad = [f"{k}M (c)" for (ss, k), v in checks.items() if ss == s and not v["c"]["ok"]]
        if bad:
            out["excluded"][s] = "(c) 걸림: " + ", ".join(bad)
    if any(v["defect"]["hit"] for v in checks.values()):
        out.update(stop=True, defect=True)
        out["why"].append("결함(얼기·잠·COVER·마스크 밖 SHELTER) — 모든 학습을 멈추고 고친다")
    k_last = max(at)
    last = {s: checks.get((s, k_last)) for s in seeds}
    if all(v is not None for v in last.values()) and last:
        if not any(v["a"]["ok"] for v in last.values()):
            out["stop"] = True
            out["why"].append(f"{k_last}M 에서 모든 시드가 (a) 에서 움직이지 않았다 — '못 배움' (R6 실패로 보고)")
        live = [s for s in seeds if s not in out["excluded"]]
        if live and all(not last[s]["b"]["ok"] for s in live):
            out["stop"] = True
            out["why"].append(f"{k_last}M 에서 남은 시드 모두 (b) 걸림 — 멈추고 관측 25 대안을 사람에게 묻는다")
    if seeds and len(out["excluded"]) == len(seeds):
        out["stop"] = True
        out["why"].append("모든 R6 시드가 (c) 로 빠졌다 — R6 실패로 보고")
    return out


# --------------------------------------------------------------------- #
# 고르기 (사전 등록 6절)
# --------------------------------------------------------------------- #

def select_key(res: dict, model_seed: int) -> tuple:
    """고르기 순서: 숨음 비율(쫓긴 도망 가운데, 전체 합) 큰 쪽 → 잡힌 몫 작은 쪽 → 굶은 몫 작은 쪽 → 모델 시드 작은 쪽 (LIVE_GATE 4절과 같은 잣대)."""
    f, p = lv.flight_pooled(res), re_.pooled(res)
    h = f["hide_share"]
    return (-(h if h == h else -1.0), p["caught"], p["starved"], int(model_seed))


# --------------------------------------------------------------------- #
# 판정 (사전 등록 4절)
# --------------------------------------------------------------------- #

def route_seed(res: dict) -> dict:
    """시드 → 길 지킴 재료 (지역 셋 합): flee·live (GT), truncated (GTr), refled (GR — 길 켬 세계만)."""
    out: dict = {}
    for w in res["worlds"]:
        f = lv.flight_of(w)
        a = out.setdefault(int(w["seed"]), dict(flee=0, live=0, truncated=0, refled=0, route=True))
        a["flee"] += int(f["flee_steps"])
        a["live"] += int(f["live_steps"])
        a["truncated"] += int(f["n"]["truncated"])
        r = f.get("route")
        if r is None:
            a["route"] = False
        else:
            a["refled"] += int(r["refled"])
    return out


def route_guards(cand: dict, cur: dict) -> dict:
    """설계 12절 길 지킴 (N, 짝 t < +t_crit(n − 1)): GT 사슴-분당 총 도주 초(= 60 × 실행 FLEE 사슴-스텝 ÷ 산 사슴-스텝 — GV 의 60 배라 t 가 같다),
    GTr 잘린 도망 수, GR 끝난 뒤 5 초(38 스텝) 안 다시 시작한 도망 수. 시드마다 지역 셋 합."""
    a, b = route_seed(cand), route_seed(cur)
    out = {}
    for name, fn, why in (("GT_flight_time", lambda x: 60.0 * x["flee"] / x["live"] if x["live"] else 0.0, "사슴-분당 총 도주 초 (잡힘·잘림 포함)"),
                          ("GTr_truncated", lambda x: float(x["truncated"]), "잘린 도망 수"),
                          ("GR_reflee", lambda x: float(x["refled"]), "끝난 뒤 5 초 안 다시 도망 수")):
        if name == "GR_reflee" and not all(x["route"] for x in list(a.values()) + list(b.values())):
            out[name] = dict(ok=False, rule="길 기록(flight.route)이 없는 세계가 있다 — 두 판 모두 길 켬 세계여야 한다 (통과로 두지 않는다)")
            continue
        q = re_.paired({s: fn(v) for s, v in a.items()}, {s: fn(v) for s, v in b.items()})
        T = lv.t_crit(int(q["n"]) - 1) if q["n"] >= 2 else float("nan")
        out[name] = dict(q, ok=_ok_t(q, q["t"] < T), rule=f"N: {why} 짝 t < +{T:.3f}")
    return out


def region_res(res: dict, region: str) -> dict:
    return dict(meta=res.get("meta", {}), worlds=[w for w in res["worlds"] if w["region"] == region])


def chase_decomp(cand: dict, cur: dict) -> dict:
    """보고만: 쫓긴 시간(스스로 벗어난 도망, 전체 합) 차이 = 끝 까닭 섞임이 바뀐 몫 Σ(s_R6 − s_0)·m_0 + 같은 까닭 안에서 짧아진 몫 Σ s_R6·(m_R6 − m_0)."""
    own = tuple(lv.LIVE["flight_own"])

    def parts(res):
        n, ct = {}, {}
        for w in res["worlds"]:
            f = lv.flight_of(w)
            for c in own:
                n[c] = n.get(c, 0) + int(f["n"][c])
                ct[c] = ct.get(c, 0) + int(f["contact"][c])
        tot = sum(n.values())
        share = {c: lv.ratio(n[c], tot) for c in own}
        mean = {c: lv.ratio(ct[c] * STEP_S, n[c]) for c in own}
        return share, mean, lv.ratio(sum(ct.values()) * STEP_S, tot)

    sa, ma, ta = parts(cand)
    sb, mb, tb = parts(cur)
    z = lambda x: 0.0 if x != x else x  # noqa: E731
    mix = sum(z((sa[c] - sb[c]) * mb[c]) for c in own)
    within = sum(z(sa[c] * (ma[c] - mb[c])) for c in own)
    return dict(total=ta - tb, mix=mix, within=within, cand=dict(share=sa, mean=ma, all=ta), cur=dict(share=sb, mean=mb, all=tb))


def a5_check(model: Path, out_dir: Path = BRAINS) -> dict:
    """내보내기 확인 A5: 두뇌 파일을 쓰고(export_weights_v3.export_brain_file — 골든 세계는 관측 24 거울) 다시 읽어 확인(adapt.verify_brain_file:
    가중치 sha256·골든 로짓 오차 ≤ 허용·행동 같음·유한) + 계약(관측 24·판 4·해시 0xe302dee198197444)."""
    import export_weights_v3 as ex

    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"{Path(model).stem}.json"
    d = ex.export_brain_file(Path(model), f)
    v = ad.verify_brain_file(f)
    v["contract_ok"] = bool(str(d.get("contract_hash")) == CONTRACT_ROUTE and int(d.get("obs_dim", 0)) == 24 and int(d.get("mask_version", 0)) == 4)
    v.update(contract_hash=str(d.get("contract_hash")), obs_dim=int(d.get("obs_dim", 0)), mask_version=int(d.get("mask_version", 0)))
    v["ok"] = bool(v["ok"] and v["finite"] and v["contract_ok"])
    return v


GUARDS = ("GH_flight_caught", "GN_caught", "GN_starved", "GN_alive", "GF_flight_starts", "GV_flee_time", "GC_flight_unsafe", "GT_flight_time",
          "GTr_truncated", "GR_reflee", "GG_caught", "GG_starved", "GG_alive", "GG_chase", "G4_catch_in_shelter", "G5_stuck", "G6_no_exploit", "A5_export")


def judge(N: dict, G: dict, stuck: dict, a5: dict | None, off: dict | None = None, rule: dict | None = None) -> dict:
    """R6 판정 (사전 등록 4절). N·G = {'candidate': R6 판, 'current': route0 판}, stuck = {'candidate', 'current'} 끼임 판. a5 = a5_check 결과(None 이면
    A5 를 통과로 두지 않는다). off·rule = 같은 N 판정 시드의 대조 '길 끔'·손 규칙 '늘 SHELTER' 판(보고만).
    1차 P1 = live.gate_live 의 P1_N_hide (숨음 비율 짝 차이 > 0 ∧ t ≥ +t_crit(n₁ − 1) — n₁ 100 이면 +1.984), 지킴 = GH·GN·GF·GV·GC(live.gate_live) +
    GT·GTr·GR(route_guards) + GG·G4·G5·G6(live.gate_live) + A5. R_check(재현 확인)는 이 판정에 없다(스냅숏 거울 세계 그대로 — 실시간 관문 몫)."""
    g = lv.gate_live(dict(N=N, G=G), stuck, None)
    c = {k: v for k, v in g["criteria"].items() if k != "R_check"}
    c.update(route_guards(N["candidate"], N["current"]))
    c["A5_export"] = (dict(a5, rule="두뇌 파일 다시 읽기: sha256·골든 로짓 오차 ≤ 허용·행동 같음·유한·관측 24·판 4·계약 0xe302dee198197444")
                      if a5 is not None else dict(ok=False, rule="A5 를 하지 않았다 (통과로 두지 않는다)"))
    p1 = c["P1_N_hide"]
    bad = [k for k in GUARDS if c.get(k, {}).get("ok") is not True]
    if not p1["ok"]:
        verdict, why = "기각", f"1차 P1 실패: 숨음 비율 R6 {lv.pct(p1['a'], 2)} 대 route0 {lv.pct(p1['b'], 2)} (짝 t {lv.tfmt(p1['t'])}, 시드 {p1['n']})"
    elif bad:
        verdict, why = "기각", "지킴 실패: " + ", ".join(bad)
    else:
        verdict, why = "통과", "1차 P1(숨음 비율)·지킴 모두 통과"
    rep: dict = dict(chase=c.pop("REPORT_N_chase", None), flight={w: g["report"]["flight"][w] for w in ("N", "G")},
                     pooled_N=g["report"]["pooled_N"], pooled_G=g["report"]["pooled_G"],
                     route=dict(candidate=route_pooled(N["candidate"]), current=route_pooled(N["current"])),
                     chase_decomp=chase_decomp(N["candidate"], N["current"]), regions={})
    for r in REGIONS:
        a, b = region_res(N["candidate"], r), region_res(N["current"], r)
        if not a["worlds"]:
            continue
        rep["regions"][r] = dict(hide=lv.hide_pair(a, b, "hide"), caught_ratio=lv.hide_pair(a, b, "caught"),
                                 caught=re_.paired(re_.per_seed(a, "caught"), re_.per_seed(b, "caught")), route=route_pooled(a))
    for name, other in (("off", off), ("rule", rule)):
        if other is None:
            continue
        rep[name] = dict(hide=lv.hide_pair(N["candidate"], other, "hide"), caught_ratio=lv.hide_pair(N["candidate"], other, "caught"),
                         caught=re_.paired(re_.per_seed(N["candidate"], "caught"), re_.per_seed(other, "caught")),
                         chase=lv.flight_pair(N["candidate"], other), flight=lv.flight_pooled(other), meta=other.get("meta"))
    return dict(verdict=verdict, passed=verdict == "통과", why=why, criteria=dict(P1_N_hide=p1, **{k: c[k] for k in GUARDS if k in c}),
                n=g["n"], t_crit=g["t_crit"], n_g=g["n_g"], t_crit_g=g["t_crit_g"], n_flight=g["n_flight"], t_crit_flight=g["t_crit_flight"],
                dropped_flight=g["dropped_flight"], report=rep, early=EARLY)


RATIO_KEYS = ("P1_N_hide", "GH_flight_caught", "GN_caught", "GN_starved", "GN_alive", "GV_flee_time", "GC_flight_unsafe", "GG_caught", "GG_starved",
              "GG_alive")                              # 몫 칸 (% 로 적는다) — 그 밖의 짝 칸은 수·초


def _cell(k: str, v: dict) -> tuple[str, str, str, str]:
    """판정 표 한 줄의 R6 · route0 · 차이 · t 칸."""
    if "diff" in v and "a" in v:
        if k in RATIO_KEYS:
            return f"{v['a'] * 100:.2f}%", f"{v['b'] * 100:.2f}%", f"{v['diff'] * 100:+.2f}%p", lv.tfmt(v["t"])
        return f"{v['a']:.4f}", f"{v['b']:.4f}", f"{v['diff']:+.4f}", lv.tfmt(v["t"])
    if k == "G4_catch_in_shelter":
        return f"N {v.get('N')} · G {v.get('G')}", "", "", ""
    if k == "G5_stuck" and "candidate" in v:
        a, b = v["candidate"], v["current"]
        return f"사슴 {a['deer']} · 늑대 {a['wolf']}", f"사슴 {b['deer']} · 늑대 {b['wolf']}", "", ""
    if k == "G6_no_exploit" and "beh" in v:
        bh = v["beh"]
        return (f"은신처 안 {v['shelter'] * 100:.2f}% · 먹기 {bh['graze'] * 100:.1f}% · 도망 {bh['flee'] * 100:.1f}% · 숨기 {bh['hide'] * 100:.1f}%",
                f"은신처 안 {v['shelter_current'] * 100:.2f}%", "", "")
    if k == "A5_export" and "golden" in v:
        return (f"sha256 {'같음' if v['sha256_ok'] else '다름'} · 골든 {v['golden']} 줄 로짓 오차 {v['max_logit_err']:.2e} (허용 {v['tolerance']:.0e}) · "
                f"행동 {'같음' if v['actions_ok'] else '다름'} · 계약 {v.get('contract_hash')} 관측 {v.get('obs_dim')} 판 {v.get('mask_version')}", "", "", "")
    val = {x: y for x, y in v.items() if x not in ("ok", "rule")}
    return json.dumps(lv.jsonable(val), ensure_ascii=False)[:160], "", "", ""


def fmt_judge(res: dict, head: str = "") -> str:
    L = [f"# R6 판정 — {res['verdict']}" + (f" ({head})" if head else ""), "",
         f"- {res['why']}",
         f"- N 시드 {res['n']} (문턱 t_crit {res['t_crit']:.3f}), 숨음 비율 짝 시드 {res['n_flight']} (문턱 {res['t_crit_flight']:.3f}, 빠진 시드 "
         f"{res['dropped_flight']}), G 시드 {res['n_g']} (문턱 {res['t_crit_g']:.3f})", "",
         "| 기준 | R6 | route0 | 차이 | t | 규칙 | 통과 |", "|---|---|---|---|---|---|---|"]
    for k, v in res["criteria"].items():
        a, b, d, t = _cell(k, v)
        L.append(f"| {k} | {a} | {b} | {d} | {t} | {v.get('rule', '')} | {'예' if v.get('ok') else '아니오'} |")
    rep = res["report"]
    L += ["", "## 보고만 (판정에 쓰지 않음)", ""]
    ch = rep.get("chase")
    if ch:
        L.append(f"- N 쫓긴 시간(스스로 벗어난 도망, 시드 평균): R6 {ch['a']:.3f} 초 · route0 {ch['b']:.3f} 초 (차이 {ch['diff']:+.3f}, t {lv.tfmt(ch['t'])}, 시드 {ch['n']})")
    dc = rep["chase_decomp"]
    L.append(f"- 쫓긴 시간 전체 합 차이 {dc['total']:+.3f} 초 = 끝 까닭 섞임 {dc['mix']:+.3f} + 같은 까닭 안 {dc['within']:+.3f}")
    for w in ("N", "G"):
        f = rep["flight"][w]
        for who in ("candidate", "current"):
            x = f[who]
            L.append(f"- {w} {('R6' if who == 'candidate' else 'route0')}: 쫓긴 도망 {x['chased']} · 숨음 {x['hidden']} ({lv.pct(x['hide_share'], 2)}) · "
                     f"잡힘 비율 {lv.pct(x['caught_share_chased'], 2)} · 은신처 끝 뒤 10 초 안 잡힘 {x['cover_then_caught']} · 굶음 {x['cover_then_starved']} · "
                     f"지켜보는 중 판 끝 {x['watching']}")
    for who in ("candidate", "current"):
        s = rep["route"][who]
        L.append(f"- 길 ({'R6' if who == 'candidate' else 'route0'}, N): SHELTER 몫 {s['shelter_share']:.4f} · 도망 하나당 결정 {s['per_flight_decisions']:.3f} · "
                 f"다시 고름 {s['per_flight_redecide']:.4f} · 무효 {s['per_flight_invalid']:.4f} · 길 바꿈 {s['per_flight_switches']:.4f}")
    L += ["", "| 지역 | 숨음 비율 R6 − route0 (t) | 잡힘 비율 (t) | 잡힌 몫 (t) | R6 SHELTER 몫 |", "|---|---|---|---|---|"]
    for r, x in rep["regions"].items():
        L.append(f"| {r} | {x['hide']['diff'] * 100:+.2f}%p ({lv.tfmt(x['hide']['t'])}) | {x['caught_ratio']['diff'] * 100:+.2f}%p ({lv.tfmt(x['caught_ratio']['t'])}) | "
                 f"{x['caught']['diff'] * 100:+.2f}%p ({lv.tfmt(x['caught']['t'])}) | {x['route']['shelter_share']:.4f} |")
    L.append("")
    for name, label in (("off", "대조 '길 끔'"), ("rule", "손 규칙 '늘 SHELTER'")):
        x = rep.get(name)
        if x is None:
            continue
        L.append(f"- R6 − {label}: 숨음 비율 {x['hide']['diff'] * 100:+.2f}%p (t {lv.tfmt(x['hide']['t'])}) · 잡힘 비율 {x['caught_ratio']['diff'] * 100:+.2f}%p "
                 f"(t {lv.tfmt(x['caught_ratio']['t'])}) · 잡힌 몫 {x['caught']['diff'] * 100:+.2f}%p (t {lv.tfmt(x['caught']['t'])}) · 쫓긴 시간 "
                 f"{x['chase']['diff']:+.3f} 초 (t {lv.tfmt(x['chase']['t'])})")
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def same_meta(path: Path, want: dict) -> bool:
    """이미 있는 판 파일이 같은 두뇌(sha1)·쓰임·시드·길이·세계 키·탐침·셈 길로 잰 것인가 (판정·고르기 이어 돌리기)."""
    if not path.exists():
        return False
    m = load(path).get("meta") or {}
    return all(m.get(k) == want.get(k) for k in ("use", "seeds", "steps", "model_sha1", "sets", "probe", "flight_cost", "code"))


def ensure_run(info, text, use, workers, name, out_dir=OUT, probe=False, flight_cost=0.0, plan=None) -> dict:
    """판 파일이 같은 조건으로 이미 있으면 읽고, 없으면 돌려 쓴다."""
    plan = plan or use_plan(use)
    spec = resolve_model(text)
    path = Path(out_dir) / f"{name}.json"
    want = dict(use=plan["use"], seeds=plan["seeds"], steps=plan["steps"], model_sha1=hashlib.sha1(Path(spec["path"]).read_bytes()).hexdigest()[:12],
                sets=spec["sets"], probe=bool(probe), flight_cost=float(flight_cost) if probe else None, code=code_tags())
    if same_meta(path, want):
        print(f"  {name}: 같은 조건의 판이 있다 — 다시 쓴다 ({lv.path_text(path)})", flush=True)
        return load(path)
    print(f"  {name}: {text} · {plan['use']} 시드 {plan['seeds'][0]}~{plan['seeds'][-1]} × 지역 {len(info['regions'])} × {plan['steps']} 스텝"
          f"{' · 탐침' if probe else ''}", flush=True)
    res = run_model(info, text, plan, workers, probe, flight_cost, name)
    save(res, path)
    return res


def cmd_run(a) -> int:
    seeds = parse_seeds(a.seeds) if a.seeds else None
    plan = use_plan(a.use, seeds, a.steps)
    info = prepare_info(a.out_dir)
    res = ensure_run(info, a.model, a.use, a.workers, a.name, a.out_dir, a.probe, a.flight_cost, plan)
    if "worlds" in res:
        p, f = re_.pooled(res), lv.flight_pooled(res)
        line = (f"{a.name}: 세계 {p['worlds']} · 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} · 쫓긴 도망 {f['chased']} 숨음 비율 "
                f"{lv.pct(f['hide_share'], 2)} 잡힘 비율 {lv.pct(f['caught_share_chased'], 2)} · 은신처 안 잡힘 {p['catch_cover']}")
        if a.probe:
            q = probe_pooled(res)
            line += (f" · π′(SHELTER) {q['pe_shelter']:.4f} (두 칸 결정 {q['two_n']}) · 도주 스텝 설명 분산 "
                     + " ".join(f"λ{k} {v:+.4f}" for k, v in q["ev"].items()) + f" (표본 {q['ev_n']})")
        print(line, flush=True)
    else:
        print(f"{a.name}: 끼임 {re_.stuck_counts(res)}", flush=True)
    return 0


def cmd_check(a) -> int:
    r = early_check(load(a.run), load(a.base), a.lam)
    text = fmt_check(Path(a.run).stem, r)
    print(text)
    return 0 if r["passed"] else 1


def _smoke_plans(a) -> dict | None:
    """--smoke 시드 --smoke-steps 길이 → 쓰임마다 스모크 계획 (도구 확인 — 판정 아님). 없으면 None (사전 등록 계획)."""
    if not a.smoke:
        return None
    seeds = parse_seeds(a.smoke)
    return {u: smoke_plan(u, seeds, a.smoke_steps) for u in USES}


def model_seed_of(label: str) -> int:
    """실행 이름의 모델 시드 (v3_r6_g995_s2_20m → 2). 없으면 0."""
    import re

    m = re.search(r"_s(\d+)(?:_|$)", label)
    return int(m.group(1)) if m else 0


FINAL_RE = r"^v3_r6_g995_s(\d+)_20m$"                 # 고르기 후보 = R6 본 학습의 마지막 모델만 (사전 등록 6절 — 중간 체크포인트·대조는 받지 않는다)


def select_guard(models: list, early_main: Path | None = None) -> None:
    """사전 등록 6절 막기: 후보는 R6 본 학습의 마지막 모델(v3_r6_g995_s<s>_20m.zip)만, 본 학습 점검(logs/early_main.json)이 제외한 시드는 받지 않는다."""
    import re

    early_main = HERE.parent / "logs" / "early_main.json" if early_main is None else Path(early_main)
    excluded = {}
    if early_main.exists():
        excluded = (json.loads(early_main.read_text(encoding="utf-8")).get("rules") or {}).get("excluded") or {}
    for m in models:
        stem = Path(m).stem
        hit = re.match(FINAL_RE, stem)
        if not hit:
            raise SystemExit(f"고르기 후보 {m} 는 R6 본 학습의 마지막 모델(v3_r6_g995_s<시드>_20m.zip)이 아니다 (사전 등록 6절)")
        if f"s{hit.group(1)}" in excluded:
            raise SystemExit(f"{m}: 본 학습 점검이 제외한 시드다 — {excluded[f's' + hit.group(1)]} ({lv.path_text(early_main)}, 사전 등록 5-3)")


def picked_model(select_txt: Path | None = None) -> str | None:
    """logs/select.txt 끝의 '고른 모델: …' (없으면 None)."""
    p = HERE.parent / "logs" / "select.txt" if select_txt is None else Path(select_txt)
    if not p.exists():
        return None
    for line in reversed(p.read_text(encoding="utf-8").splitlines()):
        if line.startswith("고른 모델: "):
            return line[len("고른 모델: "):].strip()
    return None


def cmd_select(a) -> int:
    info = prepare_info(a.out_dir)
    sp = _smoke_plans(a)
    plan = sp["select"] if sp else None
    if not sp:
        select_guard(a.models)
    rows = []
    for m in a.models:
        spec = resolve_model(m)
        res = ensure_run(info, m, "select", a.workers, f"select_{spec['label']}", a.out_dir, plan=plan)
        rows.append((select_key(res, model_seed_of(spec["label"])), m, res))
    base = ensure_run(info, "route0", "select", a.workers, "select_route0", a.out_dir, plan=plan)
    rows.sort(key=lambda x: x[0])
    lines = ["| 모델 | 숨음 비율(전체 합) | 잡힌 몫 | 굶은 몫 |", "|---|---|---|---|"]
    for key, m, res in rows + [(select_key(base, -1), "route0 (보고만)", base)]:
        lines.append(f"| {m} | {lv.pct(-key[0], 2)} | {key[1]:.4f} | {key[2]:.4f} |")
    lines.append("")
    lines.append(f"고른 모델: {rows[0][1]}")
    text = "\n".join(lines)
    print(text)
    logs = Path(a.out_dir) if sp else HERE.parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "select.txt").write_text(text + "\n", encoding="utf-8")
    return 0


def cmd_judge(a) -> int:
    sp = _smoke_plans(a) or {}
    if not sp:
        # 사전 등록 6·7절: 고른 모델 하나만 판정한다 (logs/select.txt 의 '고른 모델' 과 같은 파일이어야 한다)
        pk = picked_model()
        if pk is None:
            raise SystemExit("logs/select.txt 에 고른 모델이 없다 — 먼저 r6_eval.py select (사전 등록 6절)")
        same = Path(resolve_model(pk)["path"]).resolve() == Path(resolve_model(a.model)["path"]).resolve()
        if not same:
            raise SystemExit(f"--model {a.model} 은 고른 모델 {pk} 가 아니다 (사전 등록 6·7절 — 고른 모델 하나만 판정한다)")
    info = prepare_info(a.out_dir)
    W = a.workers
    runs = {}
    for key, text, use, name in (("N_r6", a.model, "judge_n", "judge_r6_N"), ("N_base", "route0", "judge_n", "judge_route0_N"),
                                 ("G_r6", a.model, "judge_g", "judge_r6_G"), ("G_base", "route0", "judge_g", "judge_route0_G"),
                                 ("S_r6", a.model, "stuck", "stuck_r6"), ("S_base", "route0", "stuck", "stuck_route0")):
        runs[key] = ensure_run(info, text, use, W, name, a.out_dir, plan=sp.get(use))
    off = ensure_run(info, a.off, "judge_n", W, "judge_off_N", a.out_dir, plan=sp.get("judge_n")) if a.off else None
    rule = ensure_run(info, "shelter_rule", "judge_n", W, "judge_rule_N", a.out_dir, plan=sp.get("judge_n")) if not a.no_rule else None
    a5 = a5_check(resolve_model(a.model)["path"], Path(a.out_dir) / "brains" if sp else BRAINS)
    res = judge(dict(candidate=runs["N_r6"], current=runs["N_base"]), dict(candidate=runs["G_r6"], current=runs["G_base"]),
                dict(candidate=runs["S_r6"], current=runs["S_base"]), a5, off, rule)
    res["models"] = dict(r6=a.model, base="route0", off=a.off, rule=None if a.no_rule else "shelter_rule")
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
    r.add_argument("--model", required=True, help="route0 · obs21zero · shelter_rule · 모델 zip")
    r.add_argument("--name", required=True)
    r.add_argument("--probe", action="store_true")
    r.add_argument("--flight-cost", type=float, default=0.0)
    r.add_argument("--seeds", default=None, help="smoke 만")
    r.add_argument("--steps", type=int, default=None, help="smoke 만")
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    c.add_argument("--base", required=True)
    c.add_argument("--lam", type=float, required=True, choices=EV_LAMS[:-1], help="점검 모델의 학습 GAE λ ((b) 의 수익 목표)")
    s = sub.add_parser("select")
    s.add_argument("--models", nargs="+", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--model", required=True)
    j.add_argument("--off", default=None, help="대조 '길 끔' 모델 (보고만)")
    j.add_argument("--no-rule", action="store_true", help="'늘 SHELTER' 보고 줄을 돌리지 않는다")
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
