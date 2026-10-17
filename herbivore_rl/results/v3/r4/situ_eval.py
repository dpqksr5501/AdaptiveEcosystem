"""v3 R4 보고용 상황별 결정 도구 (사전 등록 PREREG.md 4절 '보고만' — 나무 곁 결정 S5·상황별 행동 몫). 판정에 쓰지 않는다.

판정 전에 만들었다(2026-10-18, PREREG 변경 기록 (3)). 판정 도구 r4_eval.py 와 같은 세계(판정 세계 J = configs/v3_wild3_mirror.yaml × 지역 셋,
사슴 128, 늑대 식사 5초, 부활 없음, 두뇌 argmax)를 같은 실행기(run_mirror.run_world, 진단 켬)로 돌리고 진단만 더 모은다(동역학과 무관 —
그래서 같은 시드면 잡힘·굶음·산 수가 r4_eval 판과 같아야 한다. report 가 이것을 확인한다).

    # herbivore_rl/ 에서
    python results/v3/r4/situ_eval.py run --model <모델.zip 또는 r1bf> --seeds 33000-33099 --steps 7200 --workers 12 --name situ_r4_16m
    python results/v3/r4/situ_eval.py report --r4 runs/situ_r4_16m.json --base runs/situ_base_16m.json \
        --check-r4 runs/judge_r4_16m.json --check-base runs/judge_base_16m.json --out results/v3/r4/situ.md

정의(결정 = 산 사슴의 한 스텝 행동, 상황은 그 결정을 내린 관측의 상태 = 스텝 앞 기하):
- 늑대를 앎 = 깨어 있는 늑대 하나라도 보거나 들음(wf_pvis — 관측 pred_count 와 같은 보임). 거리 = 아는 늑대 가운데 가장 가까운 것, 띠 < 15 m·15~30 m·30 m 이상.
- 나무 곁 = 사슴 중심이 나무 원판 가장자리에서 5 m(2.5 단위) 안(원판 중심 거리 − 반지름 ≤ 2.5). 메마른 땅은 원판이 없다.
- 날씨 = 지역(메마른 땅 맑음·숲 비·고지 눈 — 지역마다 늘 같다).
- 두뇌 결정 = 도주 반사가 덮지 않은 스텝(스텝 앞 wf_mode 가 도주·웅크림이 아님 — world.py 가 그때만 두뇌 요청을 쓴다). 상황 표('모든 결정'·'반사가 덮음' 줄 밖)와
  S5 는 두뇌 결정만 센다. 행동 = 그 스텝에 실제로 한 행동(arbitrate 의 붙잡기 포함 — run_mirror 진단 beh_steps 와 같은 칸).
- 나무 곁 결정 S5(계획 RL_V3_R4_PLAN.md 6절): 나무 곁에서 늑대를 안 두뇌 결정 가운데, 그 결정 뒤 10초(75스텝, 한 스텝 8/60초) 안에 그 사슴이 잡힌 몫.
  견줌 줄: 나무 지역(숲·고지)에서 나무 곁이 아닌 곳에서 늑대를 안 결정. 짝 t 는 시드 단위(두 판 모두 결정이 있는 시드만).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (HERE.parent, ROOT, ROOT / "results" / "v3" / "mirror"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import r4_eval as E  # noqa: E402

STEP_S = 8.0 / 60.0
WIN10 = int(round(10.0 / STEP_S))          # 10초 = 75 스텝
NEAR_TREE = 2.5                             # 5 m (단위, 1 단위 = 2 m)
BAND_U = (7.5, 15.0)                        # 15 m·30 m (단위)
SITS = ("all", "reflex", "knows", "knows_lt15", "knows_15_30", "knows_ge30", "unaware", "tree_all", "tree_knows", "open_knows", "open_all")


def _situ_diag_class():
    import run_mirror as rm

    class SituDiag(rm._Diag):
        def __init__(self, w):
            super().__init__(w)
            self.cnt = {k: np.zeros(5, dtype=np.int64) for k in SITS}
            self.ring_t = np.zeros((w.N, WIN10 + 1), dtype=bool)   # 나무 곁 + 앎 결정(지난 76 스텝)
            self.ring_o = np.zeros((w.N, WIN10 + 1), dtype=bool)   # 나무 곁 아님 + 앎 결정(나무 있는 세계만)
            self.s5 = dict(tree_dec=0, tree_caught10=0, open_dec=0, open_caught10=0)
            self.has_trees = bool(len(w.obstacles))
            self.prev = self._state(w)

        @staticmethod
        def _state(w):
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
            return dict(dm=dm, knows=np.isfinite(dm), tree=tree, ovr=ovr.copy())

        def after(self, w, live_before):
            super().after(w, live_before)
            st, beh, L = self.prev, w._rs.behavior, live_before
            kn, dm, tr = st["knows"], st["dm"], st["tree"]
            A = L
            L = L & ~st["ovr"]                  # 아래 상황은 두뇌 결정만
            masks = dict(all=A, reflex=A & st["ovr"], knows=L & kn, knows_lt15=L & kn & (dm < BAND_U[0]), knows_15_30=L & kn & (dm >= BAND_U[0]) & (dm < BAND_U[1]),
                         knows_ge30=L & kn & (dm >= BAND_U[1]), unaware=L & ~kn)
            if self.has_trees:
                masks.update(tree_all=L & tr, tree_knows=L & tr & kn, open_knows=L & ~tr & kn, open_all=L & ~tr)
            for k, m in masks.items():
                self.cnt[k] += np.bincount(beh[m], minlength=5)
            col = int(w.t) % (WIN10 + 1)
            if self.has_trees:
                self.ring_t[:, col] = L & tr & kn
                self.ring_o[:, col] = L & ~tr & kn
                self.s5["tree_dec"] += int(np.count_nonzero(self.ring_t[:, col]))
                self.s5["open_dec"] += int(np.count_nonzero(self.ring_o[:, col]))
                for i in np.flatnonzero(L & ~w.alive & (w.death_cause == 1)):
                    self.s5["tree_caught10"] += int(self.ring_t[i].sum())
                    self.s5["open_caught10"] += int(self.ring_o[i].sum())
            self.prev = self._state(w)

        def result(self, w):
            out = super().result(w)
            out["situ"] = dict(cnt={k: v.tolist() for k, v in self.cnt.items()}, s5=dict(self.s5), has_trees=self.has_trees)
            return out

    return SituDiag


def _one(job: dict) -> dict:
    import run_mirror as rm

    rm._Diag = _situ_diag_class()           # 이 워커 안에서만: 진단 모으개를 넓힌 것으로 바꾼다(동역학과 무관)
    res = rm.run_world(job)
    m, dg = res["meta"], res["meta"]["diag"]
    cause = np.asarray(m["death_cause"])
    return dict(seed=m["seed"], region=job["region"], n=m["n"], caught=int((cause == 1).sum()), starved=int((cause == 2).sum()),
                alive=int((cause == 0).sum()), shelter_steps=m["shelter_steps"], live_steps=m["live_steps"], beh_steps=dg["beh_steps"],
                catch_cover=dg["catch_cover"], catches=dg["catches"], hunt=m["hunt"], situ=dg["situ"], wall_s=m["wall_s"])


def run(model: Path, seeds, steps: int, workers: int) -> dict:
    import run_mirror as rm
    from env_v2 import rollout as ro

    cfg = rm.mirror_cfg(128, 38, E.CONFIG)
    if not cfg.v2["features"]["wild_weather"]["enabled"] or cfg.v2["features"]["integrated_stage"]["respawn"]:
        raise ValueError("판정 세계는 날씨를 켜고 부활이 없어야 한다(v3_wild3_mirror.yaml)")
    discs = E.region_discs()
    base = cfg.to_dict()
    jobs = []
    for s in seeds:
        for r in E.REGIONS:
            c = copy.deepcopy(base)
            c["v2"]["features"]["wild_weather"]["region"] = r
            c["v2"]["features"]["obstacles"]["fixed"] = discs[r]
            jobs.append(dict(cfg=c, seed=int(s), steps=int(steps), model=str(model), log_every=int(steps) + 1, diag=True, region=r))
    t0 = time.perf_counter()
    ex = ro.make_executor(min(int(workers), len(jobs)))
    if ex is None:
        worlds = [_one(j) for j in jobs]
    else:
        with ex:
            worlds = list(ex.map(_one, jobs))
    sha = hashlib.sha1(Path(model).read_bytes()).hexdigest()[:12]
    meta = dict(tool="situ_eval", config=str(E.CONFIG.relative_to(ROOT)), config_digest=rm.config_digest(cfg),
                model=str(Path(model).relative_to(ROOT)) if Path(model).is_relative_to(ROOT) else str(model), model_sha1=sha,
                seeds=[int(s) for s in seeds], regions=list(E.REGIONS), steps=int(steps), wall_s=round(time.perf_counter() - t0, 1))
    return dict(meta=meta, worlds=worlds)


# --------------------------------------------------------------------- #
# 보고
# --------------------------------------------------------------------- #


def shares(worlds, sit: str) -> tuple[dict, int]:
    c = np.sum([w["situ"]["cnt"][sit] for w in worlds], 0).astype(np.float64)
    n = float(c.sum())
    return {b: (c[i] / n if n else float("nan")) for i, b in enumerate(E.BEH)}, int(n)


def s5_per_seed(res: dict, kind: str) -> dict:
    acc: dict[int, list[int]] = {}
    for w in res["worlds"]:
        if not w["situ"]["has_trees"]:
            continue
        a = acc.setdefault(int(w["seed"]), [0, 0])
        a[0] += w["situ"]["s5"][f"{kind}_caught10"]
        a[1] += w["situ"]["s5"][f"{kind}_dec"]
    return {s: x / y for s, (x, y) in acc.items() if y > 0}


def paired_common(a: dict, b: dict) -> dict:
    keys = sorted(set(a) & set(b))
    return E.paired({k: a[k] for k in keys}, {k: b[k] for k in keys})


def pooled_s5(res: dict, kind: str) -> tuple[float, int]:
    x = sum(w["situ"]["s5"][f"{kind}_caught10"] for w in res["worlds"] if w["situ"]["has_trees"])
    y = sum(w["situ"]["s5"][f"{kind}_dec"] for w in res["worlds"] if w["situ"]["has_trees"])
    return (x / y if y else float("nan")), int(y)


def consistency(situ: dict, judge: dict) -> str:
    key = lambda w: (int(w["seed"]), w["region"])  # noqa: E731
    js = {key(w): (w["caught"], w["starved"], w["alive"], w["beh_steps"]) for w in judge["worlds"]}
    ss = {key(w): (w["caught"], w["starved"], w["alive"], w["beh_steps"]) for w in situ["worlds"]}
    if sorted(js) != sorted(ss):
        return "세계 목록이 다르다"
    bad = [k for k in js if js[k] != ss[k]]
    return "같음(세계마다 잡힘·굶음·산·행동 수)" if not bad else f"다른 세계 {len(bad)}개: {bad[:5]}"


LABEL = dict(all="모든 스텝(반사 포함)", reflex="  반사가 덮음(도주·웅크림)", knows="두뇌 결정: 늑대를 앎", knows_lt15="  늑대 < 15 m", knows_15_30="  늑대 15~30 m", knows_ge30="  늑대 30 m 이상",
             unaware="두뇌 결정: 늑대를 모름", tree_all="두뇌 결정: 나무 곁(5 m 안)", tree_knows="  나무 곁 + 늑대를 앎", open_all="두뇌 결정: 나무 지역 트인 곳", open_knows="  트인 곳 + 늑대를 앎")
REG_KO = dict(Barren="메마른 땅(맑음)", Forest="숲(비)", Highland="고지(눈)")


def report(r4: dict, base: dict, check_r4: dict | None, check_base: dict | None) -> tuple[str, dict]:
    out: dict = {"situations": {}, "regions": {}, "s5": {}}
    L = ["| 상황 | 결정 수 R4 | R4 먹기 | R4 도망 | R4 숨기 | R1b-F 먹기 | R1b-F 도망 | R1b-F 숨기 |", "|---|---|---|---|---|---|---|---|"]
    for sit in SITS:
        a, na = shares(r4["worlds"], sit)
        b, nb = shares(base["worlds"], sit)
        out["situations"][sit] = dict(r4=a, base=b, n_r4=na, n_base=nb)
        L.append(f"| {LABEL[sit]} | {na:,} | {a['graze']:.3f} | {a['flee']:.3f} | {a['hide']:.3f} | {b['graze']:.3f} | {b['flee']:.3f} | {b['hide']:.3f} |")
    L += ["", "지역(날씨)마다 — 두뇌 결정(늑대를 앎·늑대 < 15 m) / 모든 스텝:", "",
          "| 지역 | 상황 | R4 먹기 | R4 도망 | R4 숨기 | R1b-F 먹기 | R1b-F 도망 | R1b-F 숨기 |", "|---|---|---|---|---|---|---|---|"]
    for r in E.REGIONS:
        for sit in ("knows", "knows_lt15", "all"):
            a, _ = shares([w for w in r4["worlds"] if w["region"] == r], sit)
            b, _ = shares([w for w in base["worlds"] if w["region"] == r], sit)
            out["regions"].setdefault(r, {})[sit] = dict(r4=a, base=b)
            L.append(f"| {REG_KO[r]} | {LABEL[sit].strip()} | {a['graze']:.3f} | {a['flee']:.3f} | {a['hide']:.3f} | {b['graze']:.3f} | {b['flee']:.3f} | {b['hide']:.3f} |")
    L += ["", "나무 곁 결정 S5(숲·고지, 늑대를 안 두뇌 결정 뒤 10초 안에 잡힌 몫 — 보고만):", "",
          "| 결정 | R4 몫 (결정 수) | R1b-F 몫 (결정 수) | 짝 차이 (시드 단위) | t | 시드 수 |", "|---|---|---|---|---|---|"]
    for kind, lab in (("tree", "나무 곁 + 늑대를 앎"), ("open", "트인 곳 + 늑대를 앎")):
        a, na = pooled_s5(r4, kind)
        b, nb = pooled_s5(base, kind)
        p = paired_common(s5_per_seed(r4, kind), s5_per_seed(base, kind))
        out["s5"][kind] = dict(r4=a, base=b, n_r4=na, n_base=nb, paired=p)
        L.append(f"| {lab} | {a:.4f} ({na:,}) | {b:.4f} ({nb:,}) | {p['diff']:+.4f} ± {p['se']:.4f} | {p['t']:+.2f} | {p['n']} |")
    if check_r4 is not None and check_base is not None:
        out["consistency"] = dict(r4=consistency(r4, check_r4), base=consistency(base, check_base))
        L += ["", f"판정 판과 같은가: R4 {out['consistency']['r4']}, R1b-F {out['consistency']['base']}"]
    return "\n".join(L), out


def main(argv=None) -> int:
    import run_mirror as rm

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_run = sub.add_parser("run")
    a_run.add_argument("--model", required=True)
    a_run.add_argument("--seeds", required=True)
    a_run.add_argument("--steps", type=int, default=7200)
    a_run.add_argument("--workers", type=int, default=6)
    a_run.add_argument("--name", required=True)
    a_rep = sub.add_parser("report")
    for k in ("--r4", "--base"):
        a_rep.add_argument(k, required=True)
    a_rep.add_argument("--check-r4", default=None)
    a_rep.add_argument("--check-base", default=None)
    a_rep.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        res = run(E.model_path(a.model), rm.parse_seeds(a.seeds), a.steps, a.workers)
        E.OUT.mkdir(parents=True, exist_ok=True)
        out = E.OUT / f"{a.name}.json"
        out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        p = E.pooled(res)
        print(f"{a.name}: 세계 {p['worlds']}개 {res['meta']['wall_s']:.0f}초 · 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} -> {out}")
        return 0
    text, res = report(E.load(a.r4), E.load(a.base), E.load(a.check_r4) if a.check_r4 else None,
                       E.load(a.check_base) if a.check_base else None)
    print(text)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        a.out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
