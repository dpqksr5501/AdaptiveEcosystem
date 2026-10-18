"""R5 장애물 관측 분포 확인 — 새 관측 세 칸(escape_room·obstacle_near·threat_hidden)이 판정 세계와 빽빽한 숲에서 정보를 싣는지(한 끝에 붙지 않는지) 본다
(10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 RL_V2_PLAN.md 10-19 (16)).

    # herbivore_rl/ 에서
    python results/v3/r5/obs_check.py --seeds 32000-32009 --steps 7200 --workers 14
    # 분모를 바꿔 다시 재기(아래 규칙대로 한 번만)
    python results/v3/r5/obs_check.py ... --escape-norm 5 --near-norm 5 --name obs_check_e5

세계 셋 × 지역 셋(메마른 땅·숲·고지 — 그 지역 날씨, 사슴 128, 늑대 4 + 협동, 부활 없음, 16 분):
  eval         configs/v3_wild3_obs_mirror.yaml(언리얼과 같은 세계 + 관측 21) + 지역 나무 원판(results/v3/wild2/trees/tree_layout.json — 메마른 땅 0·숲 24·고지 9).
               R5 판정 세계(1차)와 같다
  dense_brush  eval + 덤불 원판(results/v3/adapt/adapt.py shrub_discs 그대로 — 1 ha 150 개, 반지름 1~2 m, 무대에 약 216 개, 지역마다 고정 배치). 적응 고리 민감도 dense 와 같은 세계
  dense_trunk  eval 의 나무 표 대신 무작위 줄기 배치(obstacles 블록 계수 그대로 — 1 ha 줄기 250 그루 반지름 0.1~0.3 m + 바위 5 개 반지름 0.5~1.5 m, 시드마다 자기 스트림
               part 0). 실제 온대림 줄기 밀도 쪽(env_v2/world.py 모듈 docstring '야생 2단계' 3 현실 근거)
두뇌는 지금 게임 두뇌 R1b-F(ckpt/v3/v3_r1_g995_s3_20m.zip, 허용 먹기·도망·숨기). 두뇌는 관측 앞 18 칸만 받는다 — 새 세 칸은 세계를 바꾸지 않으므로(동역학 그대로) 이 판의
궤적은 관측 18 세계와 같다. 시드는 학습 세계 풀 32000~32049 안에서만 쓴다(R5 고르기·판정 시드를 쓰지 않는다).

센 것: 스텝 끝 관측(다음 결정 입력)마다 산 사슴(그 스텝에 죽은 사슴 빼고) 행. 세계·지역마다 칸별 평균·0 인 몫·1 인 몫·10 칸 막대, '위협을 앎'(관측 1 > 0) 행만 따로.

분모 고치기 규칙(재기 전에 적음, 한 번만): eval 세계 지역 셋 합의 '위협을 앎' 행에서 escape_room 이나 obstacle_near 가 한 끝(0 또는 1)에 90% 이상 붙으면 그 칸은 포화다.
  1 에 포화면 분모를 절반으로, 0 에 포화면 두 배로 한 번 바꾸고 다시 잰다(두 번째 판은 결과와 함께 적고 더 바꾸지 않는다). threat_hidden 은 0/1 칸이라 분모가 없다 —
  몫만 적는다(줄기가 드문 판정 세계에서 1 이 드문 것은 세계 탓이다).
출력 results/v3/r5/<이름>.json(메타 + 세계마다 셈)·<이름>.md(표).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (ROOT, ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "adapt"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

CONFIG = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"
LAYOUT = ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
R1BF = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
REGIONS = ("Barren", "Forest", "Highland")
REGION_INDEX = {"Barren": 0, "Forest": 1, "Highland": 2}      # 적응 고리 regions.json(세션 20003)의 region_index — 덤불 배치 난수
VARIANTS = ("eval", "dense_brush", "dense_trunk")
SLOTS = ("escape_room", "obstacle_near", "threat_hidden")
BINS = 10
SEED_RANGE = (32000, 32049)                                  # 학습 세계 풀만
SAT = 0.9


def parse_seeds(text: str) -> list[int]:
    lo, _, hi = text.partition("-")
    out = list(range(int(lo), int(hi or lo) + 1))
    bad = [s for s in out if not SEED_RANGE[0] <= s <= SEED_RANGE[1]]
    if bad:
        raise SystemExit(f"시드 {bad[:3]} 는 학습 세계 풀 {SEED_RANGE[0]}~{SEED_RANGE[1]} 밖이다 — R5 고르기·판정 시드를 쓰지 않는다")
    return out


def region_discs() -> dict:
    d = json.loads(LAYOUT.read_text(encoding="utf-8"))
    return {r["region"]: [[float(v) for v in row] for row in r["discs"]] for r in d["regions"]}


class _Head18:
    """두뇌(관측 18 모델)에게 세계 관측 앞 18 칸만 보이는 얇은 창. 나머지는 세계 그대로다."""

    def __init__(self, w, k: int):
        self._w = w
        self._k = k
        self.obs_names = tuple(w.obs_names[:k])

    def observe(self):
        return self._w.observe()[:, :self._k]

    def __getattr__(self, name):
        return getattr(self._w, name)


def _blank() -> dict:
    return {s: dict(n=0, sum=0.0, at0=0, at1=0, hist=[0] * BINS) for s in SLOTS}


def _add(acc: dict, vals: np.ndarray) -> None:
    for c, s in enumerate(SLOTS):
        v = vals[:, c].astype(np.float64)
        a = acc[s]
        a["n"] += int(len(v))
        a["sum"] += float(v.sum())
        a["at0"] += int(np.count_nonzero(v == 0.0))
        a["at1"] += int(np.count_nonzero(v == 1.0))
        h, _ = np.histogram(v, bins=BINS, range=(0.0, 1.0))
        a["hist"] = [x + int(y) for x, y in zip(a["hist"], h)]


def one(job: dict) -> dict:
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import World

    t0 = time.perf_counter()
    w = World(Config(job["cfg"]), seeds=[int(job["seed"])])
    names = list(w.obs_names)
    k = names.index(SLOTS[0])
    if names[k:k + 3] != list(SLOTS) or k != 18:
        raise ValueError(f"관측 끝 세 칸이 {SLOTS} 가 아니다: {names[k:]}")
    pc = names.index("pred_count")
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, int(job["seed"]))
    ro.forward_bind(pol, _Head18(w, k))
    acc = dict(all=_blank(), threat=_blank())
    for _ in range(int(job["steps"])):
        w.step(np.asarray(pol(w.observe()[:, :k]), dtype=np.float64))
        o = w.observe()
        live = w.alive
        rows = o[live]
        _add(acc["all"], rows[:, k:k + 3])
        th = rows[:, pc] > 0.0
        _add(acc["threat"], rows[th][:, k:k + 3])
    cause = np.asarray(w.death_cause)
    return dict(variant=job["variant"], region=job["region"], seed=int(job["seed"]), discs=int(len(w.obstacles)), acc=acc,
                caught=int((cause == 1).sum()), starved=int((cause == 2).sum()), wall_s=round(time.perf_counter() - t0, 2))


def make_jobs(seeds, steps: int, escape_norm: float | None, near_norm: float | None) -> list[dict]:
    import adapt
    import run_mirror as rm
    from env.config import Config
    from env_v2.world import World

    cfg = rm.mirror_cfg(128, 38, CONFIG)
    base = cfg.to_dict()
    if escape_norm is not None:
        base["v2"]["features"]["obstacle_obs"]["escape_norm"] = float(escape_norm)
    if near_norm is not None:
        base["v2"]["features"]["obstacle_obs"]["near_norm"] = float(near_norm)
    discs = region_discs()
    probe = World(Config(copy.deepcopy(base)), seeds=[int(seeds[0])])
    covers = np.c_[probe.cov_c, probe.cov_r].tolist()           # 통합 무대 quad — 무대 크기만으로 정해진다(시드와 무관)
    size = float(probe.size)
    jobs = []
    for s in seeds:
        for v in VARIANTS:
            for r in REGIONS:
                c = copy.deepcopy(base)
                f = c["v2"]["features"]
                f["wild_weather"]["region"] = r
                if v == "dense_trunk":
                    f["obstacles"]["fixed"] = None
                else:
                    f["obstacles"]["fixed"] = copy.deepcopy(discs[r])
                    if v == "dense_brush":
                        f["obstacles"]["fixed"] = f["obstacles"]["fixed"] + adapt.shrub_discs(REGION_INDEX[r], size, covers)
                jobs.append(dict(cfg=c, seed=int(s), steps=int(steps), model=str(R1BF), variant=v, region=r))
    return jobs, base["v2"]["features"]["obstacle_obs"]


def merge(worlds: list[dict]) -> dict:
    out: dict = {}
    for wd in worlds:
        for key in ((wd["variant"], wd["region"]), (wd["variant"], "all")):
            slot = out.setdefault(key, dict(all=_blank(), threat=_blank(), worlds=0, discs=0, caught=0, starved=0))
            slot["worlds"] += 1
            slot["discs"] += wd["discs"]
            slot["caught"] += wd["caught"]
            slot["starved"] += wd["starved"]
            for sub in ("all", "threat"):
                for s in SLOTS:
                    a, b = slot[sub][s], wd["acc"][sub][s]
                    a["n"] += b["n"]
                    a["sum"] += b["sum"]
                    a["at0"] += b["at0"]
                    a["at1"] += b["at1"]
                    a["hist"] = [x + y for x, y in zip(a["hist"], b["hist"])]
    return out


def summary(m: dict) -> dict:
    res = {}
    for (v, r), slot in m.items():
        e = dict(worlds=slot["worlds"], discs_mean=slot["discs"] / max(slot["worlds"], 1), caught=slot["caught"], starved=slot["starved"])
        for sub in ("all", "threat"):
            for s in SLOTS:
                a = slot[sub][s]
                n = max(a["n"], 1)
                e[f"{sub}.{s}"] = dict(n=a["n"], mean=a["sum"] / n, at0=a["at0"] / n, at1=a["at1"] / n, hist=[x / n for x in a["hist"]])
        res[f"{v}/{r}"] = e
    return res


def saturation(res: dict) -> dict:
    """규칙(모듈 docstring): eval 세계 지역 셋 합 '위협을 앎' 행에서 한 끝 몫 ≥ 90% 인 칸."""
    e = res["eval/all"]
    out = {}
    for s in ("escape_room", "obstacle_near"):
        a = e[f"threat.{s}"]
        out[s] = dict(at0=a["at0"], at1=a["at1"], saturated=bool(a["at0"] >= SAT or a["at1"] >= SAT),
                      action=("분모 절반" if a["at1"] >= SAT else "분모 두 배" if a["at0"] >= SAT else "그대로"))
    return out


def fmt(meta: dict, res: dict, sat: dict) -> str:
    L = [f"# R5 장애물 관측 분포 — {meta['name']}", "",
         f"- 설정 `{meta['config']}`, 분모 escape_norm {meta['norms']['escape_norm']} 단위 · near_norm {meta['norms']['near_norm']} 단위, 두뇌 R1b-F, "
         f"시드 {meta['seeds'][0]}~{meta['seeds'][-1]} × 지역 셋 × {meta['steps']} 스텝, 벽시계 {meta['wall_s']} 초",
         "- 칸마다 평균 · 0 인 몫 · 1 인 몫 (산 사슴 행, 스텝 끝 관측). '위협을 앎' = 관측 1 > 0", ""]
    for sub, title in (("all", "모든 행"), ("threat", "위협을 앎")):
        L += [f"## {title}", "", "| 세계/지역 | 원판(평균) | 행 | escape_room 평균·0·1 | obstacle_near 평균·0·1 | threat_hidden 1 몫 |", "|---|---|---|---|---|---|"]
        for key, e in res.items():
            a, b, c = e[f"{sub}.escape_room"], e[f"{sub}.obstacle_near"], e[f"{sub}.threat_hidden"]
            L.append(f"| {key} | {e['discs_mean']:.0f} | {a['n']} | {a['mean']:.3f} · {a['at0']:.3f} · {a['at1']:.3f} | "
                     f"{b['mean']:.3f} · {b['at0']:.3f} · {b['at1']:.3f} | {c['at1']:.4f} |")
        L.append("")
    L += ["## 막대 (10 칸, [0, 0.1) … [0.9, 1.0], 위협을 앎)", ""]
    for key, e in res.items():
        if not key.endswith("/all"):
            continue
        for s in ("escape_room", "obstacle_near"):
            L.append(f"- {key} {s}: " + " ".join(f"{x:.3f}" for x in e[f"threat.{s}"]["hist"]))
    L += ["", "## 포화 규칙 (eval 지역 셋 합, 위협을 앎, 한 끝 ≥ 90%)", ""]
    for s, v in sat.items():
        L.append(f"- {s}: 0 몫 {v['at0']:.3f}, 1 몫 {v['at1']:.3f} → {'포화 — ' + v['action'] if v['saturated'] else '포화 아님 — 그대로'}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    from env_v2 import rollout as ro

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", default="32000-32009")
    ap.add_argument("--steps", type=int, default=7200)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--escape-norm", type=float, default=None)
    ap.add_argument("--near-norm", type=float, default=None)
    ap.add_argument("--name", default="obs_check")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    jobs, norms = make_jobs(seeds, a.steps, a.escape_norm, a.near_norm)
    t0 = time.perf_counter()
    ex = ro.make_executor(min(a.workers, len(jobs)))
    if ex is None:
        worlds = [one(j) for j in jobs]
    else:
        with ex:
            worlds = list(ex.map(one, jobs))
    res = summary(merge(worlds))
    order = [f"{v}/{r}" for v in VARIANTS for r in REGIONS + ("all",)]
    res = {k: res[k] for k in order}
    sat = saturation(res)
    meta = dict(name=a.name, config=str(CONFIG.relative_to(ROOT)).replace("\\", "/"), layout=str(LAYOUT.relative_to(ROOT)).replace("\\", "/"),
                model=str(R1BF.relative_to(ROOT)).replace("\\", "/"), norms=norms, seeds=seeds, steps=a.steps, regions=list(REGIONS),
                variants=list(VARIANTS), wall_s=round(time.perf_counter() - t0, 1))
    out = HERE.parent / f"{a.name}.json"
    out.write_text(json.dumps(dict(meta=meta, summary=res, saturation=sat,
                                   worlds=[{k: v for k, v in wd.items() if k != "acc"} for wd in worlds]), ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    (HERE.parent / f"{a.name}.md").write_text(fmt(meta, res, sat), encoding="utf-8", newline="\n")
    print(fmt(meta, res, sat))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
