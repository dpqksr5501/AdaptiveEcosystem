"""v3 R5 보고용 나무 곁 결정 도구 (사전 등록 PREREG.md 4절 B3 '나무 곁 결정' — 보고만, 판정에 쓰지 않는다).

판정 전에 만들었다(2026-10-19, PREREG 변경 기록 (2)). 판정 시드로 시험하지 않았다(시험 32080~32081).
R4 `results/v3/r4/situ_eval.py` 의 꼴(같은 실행기 run_mirror.run_world, 진단 켬, 진단 모으개만 넓힘 — 동역학과 무관)을 따르고 셋이 다르다:
  1) 두 두뇌 모두 관측 21 세계(configs/v3_wild3_obs_mirror.yaml)에서 돌린다. 관측 18 두뇌(R1b-F)는 앞 18 칸만 받는다(`SliceLearned` — 마스크는
     세계 관측의 이름으로 만들어 관측 18 세계와 같다). 두 설정은 세계가 비트 단위로 같아서(tests/test_obstacle_obs.py) R1b-F 결과가 판정 판
     (관측 18 세계)과 같아야 한다 — report 가 세계마다 잡힘·굶음·산·행동 수로 확인한다.
  2) 상황을 그 결정을 내린 관측의 장애물 세 칸으로 가른다(관측 21 세계라 두 두뇌 모두 같은 값이 있다).
  3) --world dense: 빽빽한 숲(r5_eval.py run --world dense 와 같은 세계 = 언리얼 지역 나무 원판 + 덤불 원판).

    # herbivore_rl/ 에서
    python results/v3/r5/situ_r5.py run --model <모델.zip 또는 r1bf> --world unreal --seeds 33100-33199 --steps 7200 --workers 12 --name situ_r5_16m
    python results/v3/r5/situ_r5.py report --r5 runs/situ_r5_16m.json --base runs/situ_base_16m.json --r5-dense runs/situ_r5_dense.json \
        --base-dense runs/situ_base_dense.json --check-r5 runs/judge_r5_16m.json --check-base runs/judge_base_16m.json \
        --check-r5-dense runs/dense_r5_16m.json --check-base-dense runs/dense_base_16m.json --out results/v3/r5/situ.md

정의(PREREG 4절 B3 그대로. 결정 = 산 사슴의 한 스텝, 상황은 그 결정을 내린 관측 = 스텝 앞 상태):
- 두뇌 결정 = 도주 반사가 덮지 않은 스텝(R4 situ_eval 과 같다 — 스텝 앞 wf_mode 가 도주·웅크림이 아님). 행동 = 그 스텝에 실제로 한 행동.
- 늑대를 앎 = 깨어 있는 늑대 하나라도 보거나 들음(wf_pvis — R4 situ_eval 과 같다).
- 좁은 길: 늑대를 안 두뇌 결정 가운데 escape_room < 0.25(도망 쪽 5 m 안에 원판이나 벽). 견줌 줄 escape_room ≥ 0.25.
- 가림: 늑대를 안 두뇌 결정 가운데 threat_hidden = 1. 견줌 줄 threat_hidden = 0 이면서 obstacle_near < 1(원판 가장자리 10 m 안).
- 나무 곁 S5(R4 와 같은 정의): 사슴 중심이 원판 가장자리 5 m 안(원판 중심 거리 − 반지름 ≤ 2.5 단위)에서 늑대를 안 두뇌 결정. 견줌 줄 원판이 있는 세계의
  나무 곁 아닌 곳. 원판 = 세계 원판 전부(빽빽한 숲은 덤불 포함). 원판이 없는 세계(판정 세계 메마른 땅)는 S5 에서 뺀다.
- 10초 안 잡힘 = 그 결정 뒤 75 스텝(한 스텝 8/60초, 결정 스텝 포함) 안에 그 사슴이 잡힌 몫(결정 수로 나눔).
- 짝 t 는 시드 단위(지역 셋 합, 두 판 모두 그 상황 결정이 있는 시드만).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (HERE.parent, ROOT, ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "adapt"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import r5_eval as R5E  # noqa: E402

E = R5E.R4E
CONFIG = R5E.CONFIGS[21]
STEP_S = 8.0 / 60.0
WIN10 = int(round(10.0 / STEP_S))          # 10초 = 75 스텝
NEAR_TREE = 2.5                             # 5 m (단위, 1 단위 = 2 m)
NARROW = 0.25                               # escape_room < 0.25 = 도망 쪽 5 m 안에 막힘(분모 20 m)
SITS = ("all", "reflex", "knows", "unaware", "narrow", "wide", "hidden", "seen_near", "tree", "open")
RINGS = ("narrow", "wide", "hidden", "seen_near", "tree", "open")
LABEL = dict(all="모든 스텝(반사 포함)", reflex="  반사가 덮음(도주·웅크림)", knows="두뇌 결정: 늑대를 앎", unaware="두뇌 결정: 늑대를 모름",
             narrow="좁은 길: 앎 + escape_room < 0.25 (5 m 안 막힘)", wide="  견줌: 앎 + escape_room ≥ 0.25",
             hidden="가림: 앎 + threat_hidden 1 (줄기가 늑대 눈길을 가림)", seen_near="  견줌: 앎 + 안 가림 + obstacle_near < 1 (원판 10 m 안)",
             tree="나무 곁 S5: 앎 + 원판 가장자리 5 m 안", open="  견줌: 앎 + 원판 있는 세계의 트인 곳")


# --------------------------------------------------------------------- #
# R1b-F(관측 18)를 관측 21 세계에서: 앞 18 칸만 받는다
# --------------------------------------------------------------------- #


def _slice_class():
    from env_v2 import rollout as ro

    class SliceLearned(ro.RepLearned):
        """RepLearned 와 같고, 망 입력에 세계 관측의 앞 k 칸만 넣는다. 세계 관측 이름 = 모델 관측 이름 + 장애물 세 칸이어야 한다.
        마스크는 세계 관측(이름으로 칸을 찾는다 — pred_count·threat_recency·cover_dist)으로 만들어 관측 18 세계와 같다."""

        def __init__(self, model, k: int):
            super().__init__(model)
            self.k = int(k)

        def bind_world(self, world) -> None:
            from env_v2.rep_policy import allowed_mask_of, check_mask_version, effective_allowed
            from env_v2.world import OBSTACLE_OBS_NAMES

            pol = self.model.policy
            names = tuple(world.obs_names)
            if names[:self.k] != tuple(pol.rep_obs_names) or names[self.k:] != tuple(OBSTACLE_OBS_NAMES):
                raise ValueError(f"세계 관측 {list(names)} 이 모델 관측 {list(pol.rep_obs_names)} + 장애물 세 칸이 아니다")
            check_mask_version(getattr(pol, "rep_mask_version", 1), names[:self.k])
            check_mask_version(getattr(pol, "rep_mask_version", 1), names)
            self.allowed = effective_allowed(pol.rep_allowed, world.cfg)
            self.params = {"allowed_mask": allowed_mask_of(self.allowed)}
            self.world = world

        def __call__(self, obs):
            from env_v2.rep_policy import policy_obs, rep_argmax

            m = self.mask()
            a = rep_argmax(self.model.policy, policy_obs(np.asarray(obs)[:, :self.k], m))
            self.last_mask = m
            return a.astype(np.float64)[:, None]

    return SliceLearned


# --------------------------------------------------------------------- #
# 진단 모으개 (동역학과 무관)
# --------------------------------------------------------------------- #

_CLS = None


def _situ_diag_class():
    """넓힌 진단 모으개 — 프로세스마다 한 번만 만든다(R4 situ_eval 과 같은 까닭: 잡마다 만들면 겹쳐 쌓인다)."""
    global _CLS
    if _CLS is not None:
        return _CLS
    import run_mirror as rm

    base = getattr(rm, "_Diag_orig", rm._Diag)
    rm._Diag_orig = base

    class SituDiag(base):
        def __init__(self, w):
            super().__init__(w)
            if getattr(w, "_obs_oo", None) is None:
                raise ValueError("situ_r5 는 관측 21 세계(obstacle_obs 켬)에서만 돈다")
            self.oo = int(w._obs_oo)
            self.cnt = {k: np.zeros(5, dtype=np.int64) for k in SITS}
            self.ring = {k: np.zeros((w.N, WIN10 + 1), dtype=bool) for k in RINGS}
            self.s10 = {k: [0, 0] for k in RINGS}          # [결정 수, 10초 안 잡힘]
            self.has_trees = bool(len(w.obstacles))
            self.prev = self._state(w)

        def _state(self, w):
            g, pos = w._g, w.pos
            dm = np.full(w.N, np.inf)
            if w.M and g["wf_pvis"].shape[1]:
                d = np.sqrt(((pos[:, None, :] - w.pred_pos[None, :, :]) ** 2).sum(-1))
                dm = np.where(g["wf_pvis"], d, np.inf).min(1)
            ob = w.obstacles
            if len(ob):
                de = (np.sqrt(((pos[:, None, :] - ob[None, :, :2]) ** 2).sum(-1)) - ob[None, :, 2]).min(1)
                tree = de <= NEAR_TREE
            else:
                tree = np.zeros(w.N, dtype=bool)
            wf = getattr(w, "wf_mode", None)
            if getattr(w, "_wf", None) is not None and wf is not None:
                from env_v2.world import WF_PANIC, WF_SHELTER

                ovr = (wf == WF_PANIC) | (wf == WF_SHELTER)
            else:
                ovr = np.zeros(w.N, dtype=bool)
            o = np.asarray(w.observe())[:, self.oo:self.oo + 3].astype(np.float64)     # 이 상태에서 두뇌가 받는 관측(다음 결정)
            return dict(dm=dm, knows=np.isfinite(dm), tree=tree, ovr=ovr.copy(), esc=o[:, 0].copy(), near=o[:, 1].copy(), hid=o[:, 2].copy())

        def after(self, w, live_before):
            super().after(w, live_before)
            st, beh, A = self.prev, w._rs.behavior, live_before
            kn = st["knows"]
            L = A & ~st["ovr"]                  # 두뇌 결정만
            K = L & kn
            masks = dict(all=A, reflex=A & st["ovr"], knows=K, unaware=L & ~kn,
                         narrow=K & (st["esc"] < NARROW), wide=K & (st["esc"] >= NARROW),
                         hidden=K & (st["hid"] >= 0.5), seen_near=K & (st["hid"] < 0.5) & (st["near"] < 1.0))
            if self.has_trees:
                masks.update(tree=K & st["tree"], open=K & ~st["tree"])
            else:
                masks.update(tree=np.zeros(w.N, dtype=bool), open=np.zeros(w.N, dtype=bool))
            for k, m in masks.items():
                self.cnt[k] += np.bincount(beh[m], minlength=5)
            col = int(w.t) % (WIN10 + 1)
            for k in RINGS:
                self.ring[k][:, col] = masks[k]
                self.s10[k][0] += int(np.count_nonzero(masks[k]))
            # 잡힘은 이 스텝 앞에 산 모든 사슴에서 센다(반사 중에 잡힌 사슴 포함 — 결정은 그 앞 10초 안의 두뇌 결정)
            for i in np.flatnonzero(A & ~w.alive & (w.death_cause == 1)):
                for k in RINGS:
                    self.s10[k][1] += int(self.ring[k][i].sum())
            self.prev = self._state(w)

        def result(self, w):
            out = super().result(w)
            out["situ"] = dict(cnt={k: v.tolist() for k, v in self.cnt.items()}, s10={k: list(v) for k, v in self.s10.items()},
                               has_trees=self.has_trees)
            return out

    _CLS = SituDiag
    return SituDiag


def _one(job: dict) -> dict:
    import run_mirror as rm
    from env_v2 import rollout as ro

    rm._Diag = _situ_diag_class()           # 이 워커 안에서만: 진단 모으개를 넓힌 것으로 바꾼다(동역학과 무관)
    k = job.get("obs_slice")
    orig = ro.build_policy
    if k is not None:
        cls = _slice_class()

        def build(spec, seed=0):
            if spec.get("kind") != "rep_learned" or spec.get("path") != job["model"]:
                raise ValueError(f"situ_r5 는 rep_learned 두뇌 하나만 돌린다: {spec!r}")
            return cls(ro._load_model({"model": spec["path"]}), k)

        ro.build_policy = build
    try:
        res = rm.run_world(job)
    finally:
        ro.build_policy = orig
    m, dg = res["meta"], res["meta"]["diag"]
    if dg["situ"]["cnt"]["all"] != dg["beh_steps"]:
        raise RuntimeError(f"상황 진단이 행동 수와 다르다(시드 {m['seed']} {job['region']}): {dg['situ']['cnt']['all']} != {dg['beh_steps']}")
    cause = np.asarray(m["death_cause"])
    return dict(seed=m["seed"], region=job["region"], n=m["n"], caught=int((cause == 1).sum()), starved=int((cause == 2).sum()),
                alive=int((cause == 0).sum()), shelter_steps=m["shelter_steps"], live_steps=m["live_steps"], beh_steps=dg["beh_steps"],
                catch_cover=dg["catch_cover"], catches=dg["catches"], hunt=m["hunt"], situ=dg["situ"], wall_s=m["wall_s"])


def run(model: Path, seeds, steps: int, workers: int, world: str = "unreal") -> dict:
    import adapt
    import run_mirror as rm
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import World

    if world not in R5E.WORLDS:
        raise ValueError(f"세계 {world} 는 {R5E.WORLDS} 가운데 하나다")
    d = R5E.model_obs_dim(model)
    if d not in (18, 21):
        raise ValueError(f"{model}: 관측 {d} 칸 두뇌는 받지 않는다(관측 18·21 만)")
    cfg = rm.mirror_cfg(128, 38, CONFIG)
    if not cfg.v2["features"]["wild_weather"]["enabled"] or cfg.v2["features"]["integrated_stage"]["respawn"]:
        raise ValueError("판정 세계는 날씨를 켜고 부활이 없어야 한다")
    discs = E.region_discs()
    base = cfg.to_dict()
    shrubs = None
    if world == "dense":                    # r5_eval.run --world dense 와 같은 덤불
        probe = World(Config(copy.deepcopy(base)), seeds=[int(seeds[0])])
        covers = np.c_[probe.cov_c, probe.cov_r].tolist()
        shrubs = {r: adapt.shrub_discs(R5E.REGION_INDEX[r], float(probe.size), covers) for r in E.REGIONS}
    jobs = []
    for s in seeds:
        for r in E.REGIONS:
            c = copy.deepcopy(base)
            c["v2"]["features"]["wild_weather"]["region"] = r
            c["v2"]["features"]["obstacles"]["fixed"] = discs[r] + (shrubs[r] if shrubs is not None else [])
            jobs.append(dict(cfg=c, seed=int(s), steps=int(steps), model=str(model), log_every=int(steps) + 1, diag=True, region=r,
                             obs_slice=18 if d == 18 else None))
    t0 = time.perf_counter()
    ex = ro.make_executor(min(int(workers), len(jobs)))
    if ex is None:
        worlds = [_one(j) for j in jobs]
    else:
        with ex:
            worlds = list(ex.map(_one, jobs))
    sha = hashlib.sha1(Path(model).read_bytes()).hexdigest()[:12]
    meta = dict(tool="situ_r5", config=str(CONFIG.relative_to(ROOT)), config_digest=rm.config_digest(cfg),
                model=str(Path(model).relative_to(ROOT)) if Path(model).is_relative_to(ROOT) else str(model), model_sha1=sha, obs_dim=d,
                net_input="앞 18 칸(SliceLearned)" if d == 18 else "21 칸", world=world, seeds=[int(s) for s in seeds], regions=list(E.REGIONS),
                steps=int(steps), shrubs={r: len(v) for r, v in shrubs.items()} if shrubs is not None else None,
                wall_s=round(time.perf_counter() - t0, 1))
    return dict(meta=meta, worlds=worlds)


# --------------------------------------------------------------------- #
# 보고
# --------------------------------------------------------------------- #


def shares(worlds, sit: str) -> tuple[dict, int]:
    c = np.sum([w["situ"]["cnt"][sit] for w in worlds], 0).astype(np.float64)
    n = float(c.sum())
    return {b: (c[i] / n if n else float("nan")) for i, b in enumerate(E.BEH)}, int(n)


def s10_per_seed(res: dict, kind: str) -> dict:
    acc: dict[int, list[int]] = {}
    for w in res["worlds"]:
        if kind in ("tree", "open") and not w["situ"]["has_trees"]:
            continue
        a = acc.setdefault(int(w["seed"]), [0, 0])
        a[0] += w["situ"]["s10"][kind][1]
        a[1] += w["situ"]["s10"][kind][0]
    return {s: x / y for s, (x, y) in acc.items() if y > 0}


def share_per_seed(res: dict, sit: str, b: int) -> dict:
    acc: dict[int, np.ndarray] = {}
    for w in res["worlds"]:
        acc[int(w["seed"])] = acc.get(int(w["seed"]), np.zeros(5)) + np.asarray(w["situ"]["cnt"][sit], dtype=np.float64)
    return {s: float(c[b] / c.sum()) for s, c in acc.items() if c.sum() > 0}


def pooled_s10(res: dict, kind: str) -> tuple[float, int]:
    W = [w for w in res["worlds"] if kind not in ("tree", "open") or w["situ"]["has_trees"]]
    x = sum(w["situ"]["s10"][kind][1] for w in W)
    y = sum(w["situ"]["s10"][kind][0] for w in W)
    return (x / y if y else float("nan")), int(y)


def paired_common(a: dict, b: dict) -> dict:
    keys = sorted(set(a) & set(b))
    if len(keys) < 2:
        return dict(diff=float("nan"), se=float("nan"), t=float("nan"), n=len(keys))
    return E.paired({k: a[k] for k in keys}, {k: b[k] for k in keys})


def consistency(situ: dict, judge: dict) -> str:
    key = lambda w: (int(w["seed"]), w["region"])  # noqa: E731
    js = {key(w): (w["caught"], w["starved"], w["alive"], tuple(w["beh_steps"])) for w in judge["worlds"]}
    ss = {key(w): (w["caught"], w["starved"], w["alive"], tuple(w["beh_steps"])) for w in situ["worlds"]}
    if sorted(js) != sorted(ss):
        return "세계 목록이 다르다"
    bad = [k for k in js if js[k] != ss[k]]
    return f"같음(세계 {len(js)}개마다 잡힘·굶음·산·행동 수)" if not bad else f"다른 세계 {len(bad)}개: {bad[:5]}"


def report_world(r5: dict, base: dict, title: str) -> tuple[list, dict]:
    out: dict = {"situations": {}, "s10": {}}
    L = [f"### {title}", "", "| 상황 | 결정 수 R5 | R5 먹기 | R5 도망 | R5 숨기 | 결정 수 R1b-F | R1b-F 먹기 | R1b-F 도망 | R1b-F 숨기 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for sit in SITS:
        a, na = shares(r5["worlds"], sit)
        b, nb = shares(base["worlds"], sit)
        pf = paired_common(share_per_seed(r5, sit, 1), share_per_seed(base, sit, 1))
        ph = paired_common(share_per_seed(r5, sit, 2), share_per_seed(base, sit, 2))
        out["situations"][sit] = dict(r5=a, base=b, n_r5=na, n_base=nb, paired_flee=pf, paired_hide=ph)
        L.append(f"| {LABEL[sit]} | {na:,} | {a['graze']:.3f} | {a['flee']:.3f} | {a['hide']:.3f} | {nb:,} | {b['graze']:.3f} | {b['flee']:.3f} | {b['hide']:.3f} |")
    L += ["", "행동 몫 짝 차이(시드 단위, 두 판 모두 그 상황 결정이 있는 시드):", "",
          "| 상황 | 도망 몫 R5 − R1b-F (t) | 숨기 몫 R5 − R1b-F (t) | 시드 수 |", "|---|---|---|---|"]
    for sit in ("knows",) + RINGS:
        s = out["situations"][sit]
        L.append(f"| {LABEL[sit].strip()} | {s['paired_flee']['diff']:+.4f} ({s['paired_flee']['t']:+.2f}) | "
                 f"{s['paired_hide']['diff']:+.4f} ({s['paired_hide']['t']:+.2f}) | {s['paired_flee']['n']} |")
    L += ["", "그 결정 뒤 10초(75 스텝) 안에 잡힌 몫:", "",
          "| 상황 | R5 몫 (결정 수) | R1b-F 몫 (결정 수) | 짝 차이 (시드 단위) | t | 시드 수 |", "|---|---|---|---|---|---|"]
    for kind in RINGS:
        a, na = pooled_s10(r5, kind)
        b, nb = pooled_s10(base, kind)
        p = paired_common(s10_per_seed(r5, kind), s10_per_seed(base, kind))
        out["s10"][kind] = dict(r5=a, base=b, n_r5=na, n_base=nb, paired=p)
        L.append(f"| {LABEL[kind].strip()} | {a:.5f} ({na:,}) | {b:.5f} ({nb:,}) | {p['diff']:+.5f} ± {p['se']:.5f} | {p['t']:+.2f} | {p['n']} |")
    return L, out


def report(r5, base, r5d=None, based=None, checks=None) -> tuple[str, dict]:
    L = ["# R5 나무 곁 결정 (PREREG 4절 B3 — 보고만, 판정 아님)", "",
         "두 두뇌 모두 관측 21 세계에서 돌렸다. R1b-F 는 앞 18 칸만 받는다(장애물 세 칸을 못 본다). 결정 = 반사가 덮지 않은 산 사슴의 스텝.", ""]
    out: dict = {}
    t, o = report_world(r5, base, "판정 세계 (언리얼과 같은 나무 + 날씨, 16분)")
    L += t
    out["unreal"] = o
    if r5d is not None and based is not None:
        t, o = report_world(r5d, based, "빽빽한 숲 (나무 + 덤불 약 216, 16분 — 학습에 없던 배치)")
        L += [""] + t
        out["dense"] = o
    if checks:
        out["consistency"] = {}
        L += ["", "판정·빽빽한 숲 판과 같은가(같은 시드·같은 두뇌면 같아야 한다 — R1b-F 는 관측 18 세계 판과 견줌):", ""]
        for name, (s, j) in checks.items():
            if s is None or j is None:
                continue
            out["consistency"][name] = consistency(s, j)
            L.append(f"- {name}: {out['consistency'][name]}")
    return "\n".join(L), out


def main(argv=None) -> int:
    import run_mirror as rm

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_run = sub.add_parser("run")
    a_run.add_argument("--model", required=True, help="r1bf 또는 모델 .zip 경로")
    a_run.add_argument("--seeds", required=True)
    a_run.add_argument("--steps", type=int, default=7200)
    a_run.add_argument("--workers", type=int, default=6)
    a_run.add_argument("--world", choices=R5E.WORLDS, default="unreal")
    a_run.add_argument("--name", required=True)
    a_run.add_argument("--out-dir", type=Path, default=R5E.OUT)
    a_rep = sub.add_parser("report")
    for k in ("--r5", "--base"):
        a_rep.add_argument(k, required=True)
    for k in ("--r5-dense", "--base-dense", "--check-r5", "--check-base", "--check-r5-dense", "--check-base-dense"):
        a_rep.add_argument(k, default=None)
    a_rep.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        res = run(E.model_path(a.model), rm.parse_seeds(a.seeds), a.steps, a.workers, a.world)
        a.out_dir.mkdir(parents=True, exist_ok=True)
        out = a.out_dir / f"{a.name}.json"
        out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        p = E.pooled(res)
        print(f"{a.name}: 관측 {res['meta']['obs_dim']}·{a.world} 세계 {p['worlds']}개 {res['meta']['wall_s']:.0f}초 · 잡힘 {p['caught']:.4f} "
              f"굶음 {p['starved']:.4f} 산 {p['alive']:.4f} -> {out}")
        return 0
    ld = lambda x: E.load(x) if x else None  # noqa: E731
    checks = {"R5 판정 세계": (ld(a.r5), ld(a.check_r5)), "R1b-F 판정 세계": (ld(a.base), ld(a.check_base)),
              "R5 빽빽한 숲": (ld(a.r5_dense), ld(a.check_r5_dense)), "R1b-F 빽빽한 숲": (ld(a.base_dense), ld(a.check_base_dense))}
    text, res = report(E.load(a.r5), E.load(a.base), ld(a.r5_dense), ld(a.base_dense), checks)
    print(text)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        a.out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
