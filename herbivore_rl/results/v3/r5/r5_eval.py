"""v3 R5 판정·점검·고르기 도구 (사전 등록 results/v3/r5/PREREG.md 4~7절). R4 도구(results/v3/r4/r4_eval.py)의 세계·지표·규칙을 그대로 쓰고 둘만 다르다:
  1) 두뇌의 관측 칸 수로 세계 설정을 고른다 — 관측 21 두뇌(R5)는 configs/v3_wild3_obs_mirror.yaml, 관측 18 두뇌(R1b-F)는 configs/v3_wild3_mirror.yaml.
     두 설정은 세계(이동·시선·먹이·늑대·날씨·난수)가 비트 단위로 같고 관측만 다르다(tests/test_obstacle_obs.py). 그래서 같은 시드면 같은 세계에서 짝 비교한다.
  2) --world dense: 2차(보고만) 빽빽한 숲 세계 = 언리얼 지역 나무 원판 + 덤불 원판(results/v3/adapt/adapt.py shrub_discs — 지역마다 고정 배치, 1 ha 150 개,
     반지름 1~2 m, 무대에 약 216 개). R5 학습의 무작위 숲(env_v2/vec_env.py 'v3 R5 무작위 숲 섞기')과 다른 난수로 놓은 배치라 학습에 나온 적 없는 숲이다.

    # herbivore_rl/ 에서
    python results/v3/r5/r5_eval.py run --model r1bf --seeds 32050-32059 --steps 7200 --name early_base
    python results/v3/r5/r5_eval.py run --model ckpt/v3/v3_r5_g995_s0_20m_2m.zip --seeds 32050-32059 --steps 7200 --name early_s0_2m
    python results/v3/r5/r5_eval.py check --run results/v3/r5/runs/early_s0_2m.json --base results/v3/r5/runs/early_base.json
    python results/v3/r5/r5_eval.py select --runs results/v3/r5/runs/select_s0.json ... --base results/v3/r5/runs/select_base.json
    python results/v3/r5/r5_eval.py judge --r4 runs/judge_r5_16m.json --base runs/judge_base_16m.json --r4-short runs/judge_r5_240s.json \
        --base-short runs/judge_base_240s.json --stuck-r4 runs/stuck_r5.json --stuck-base runs/stuck_base.json --out results/v3/r5/judge.md
    python results/v3/r5/r5_eval.py run --model <모델> --world dense --seeds 33100-33199 --steps 7200 --name dense_r5_16m   # 2차, 보고만
    python results/v3/r5/r5_eval.py dense --r5 runs/dense_r5_16m.json --base runs/dense_base_16m.json --out results/v3/r5/dense.md

judge 의 인자 이름(--r4·--r4-short·--stuck-r4)은 R4 도구 그대로다(R5 판을 준다). 시드: 점검 32050~32059, 고르기 32060~32079, 판정 33100~33199
(run_mirror.SEED_RANGES — R4 판정 33000~33099 는 쓰지 않는다).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import json
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (ROOT, ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "adapt"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


R4E = _module("_r4_eval_for_r5", ROOT / "results" / "v3" / "r4" / "r4_eval.py")
CONFIGS = {18: ROOT / "configs" / "v3_wild3_mirror.yaml", 21: ROOT / "configs" / "v3_wild3_obs_mirror.yaml"}
LAYOUT = R4E.LAYOUT
R1BF = R4E.R1BF
OUT = HERE.parent / "runs"
REGIONS = R4E.REGIONS
REGION_INDEX = {"Barren": 0, "Forest": 1, "Highland": 2}     # adapt.py 지역 번호(덤불 배치 난수 구분) — results/v3/r5/obs_check.py 와 같다
WORLDS = ("unreal", "dense")


def model_obs_dim(path: Path) -> int:
    """모델 zip 의 정책망 첫 층 입력 칸 수(= 관측 칸 수)."""
    import torch as th

    sd = th.load(io.BytesIO(zipfile.ZipFile(path).read("policy.pth")), map_location="cpu", weights_only=True)
    w = sd.get("mlp_extractor.policy_net.0.weight")
    if w is None:
        raise ValueError(f"{path}: 정책망 첫 층이 없다")
    return int(w.shape[1])


def config_for(model: Path) -> Path:
    d = model_obs_dim(model)
    if d not in CONFIGS:
        raise ValueError(f"{model}: 관측 {d} 칸 두뇌는 받지 않는다(관측 18·21 만)")
    return CONFIGS[d]


def run(model: Path, seeds, steps: int, workers: int, world: str = "unreal", regions=REGIONS) -> dict:
    import adapt
    import run_mirror as rm
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import World

    if world not in WORLDS:
        raise ValueError(f"세계 {world} 는 {WORLDS} 가운데 하나다")
    config = config_for(model)
    cfg = rm.mirror_cfg(128, 38, config)
    if not cfg.v2["features"]["wild_weather"]["enabled"] or cfg.v2["features"]["integrated_stage"]["respawn"]:
        raise ValueError("판정 세계는 날씨를 켜고 부활이 없어야 한다")
    discs = R4E.region_discs()
    base = cfg.to_dict()
    shrubs = None
    if world == "dense":
        probe = World(Config(copy.deepcopy(base)), seeds=[int(seeds[0])])
        covers = np.c_[probe.cov_c, probe.cov_r].tolist()           # 통합 무대 quad — 무대 크기만으로 정해진다(시드와 무관)
        shrubs = {r: adapt.shrub_discs(REGION_INDEX[r], float(probe.size), covers) for r in regions}
    jobs = []
    for s in seeds:
        for r in regions:
            c = copy.deepcopy(base)
            c["v2"]["features"]["wild_weather"]["region"] = r
            c["v2"]["features"]["obstacles"]["fixed"] = discs[r] + (shrubs[r] if shrubs is not None else [])
            jobs.append(dict(cfg=c, seed=int(s), steps=int(steps), model=str(model), log_every=int(steps) + 1, diag=True, region=r))
    t0 = time.perf_counter()
    ex = ro.make_executor(min(int(workers), len(jobs)))
    if ex is None:
        worlds = [R4E._one(j) for j in jobs]
    else:
        with ex:
            worlds = list(ex.map(R4E._one, jobs))
    sha = hashlib.sha1(Path(model).read_bytes()).hexdigest()[:12]
    meta = dict(config=str(config.relative_to(ROOT)), config_digest=rm.config_digest(cfg), model=str(Path(model).relative_to(ROOT))
                if Path(model).is_relative_to(ROOT) else str(model), model_sha1=sha, obs_dim=model_obs_dim(model), world=world,
                seeds=[int(s) for s in seeds], regions=list(regions), steps=int(steps), layout=str(LAYOUT.relative_to(ROOT)),
                shrubs={r: len(v) for r, v in shrubs.items()} if shrubs is not None else None, wall_s=round(time.perf_counter() - t0, 1))
    return dict(meta=meta, worlds=worlds)


def dense_report(r5: dict, base: dict) -> dict:
    """2차(보고만): 빽빽한 숲 세계의 짝 차이 — 잡힘·굶음·산(합쳐서·지역마다), 행동 몫, 은신처 안 몫."""
    out = {"pooled": dict(r5=R4E.pooled(r5), base=R4E.pooled(base)), "paired": {}}
    for key in ("caught", "starved", "alive", "shelter"):
        out["paired"][key] = R4E.paired(R4E.per_seed(r5, key), R4E.per_seed(base, key))
        for r in REGIONS:
            out["paired"][f"{r}_{key}"] = R4E.paired(R4E.per_seed(r5, key, r), R4E.per_seed(base, key, r))
    return out


def fmt_dense(res: dict) -> str:
    lines = ["# R5 2차 — 빽빽한 숲 세계 (보고만, 판정 아님)", "", "| 칸 | R5 − R1b-F | t | 시드 |", "|---|---|---|---|"]
    for k, p in res["paired"].items():
        lines.append(f"| {k} | {p['diff']:+.4f} | {p['t']:+.2f} | {p['n']} |")
    a, b = res["pooled"]["r5"], res["pooled"]["base"]
    lines += ["", "| 두뇌 | 잡힘 | 굶음 | 산 | 은신처 안 | 먹기 | 도망 | 숨기 |", "|---|---|---|---|---|---|---|---|"]
    for name, p in (("R5", a), ("R1b-F", b)):
        lines.append(f"| {name} | {p['caught']:.4f} | {p['starved']:.4f} | {p['alive']:.4f} | {p['shelter']:.4f} | "
                     f"{p['beh']['graze']:.4f} | {p['beh']['flee']:.4f} | {p['beh']['hide']:.4f} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    import run_mirror as rm

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_run = sub.add_parser("run")
    a_run.add_argument("--model", required=True, help="r1bf 또는 모델 .zip 경로")
    a_run.add_argument("--seeds", required=True)
    a_run.add_argument("--steps", type=int, default=7200, help="7200 = 16분, 1800 = 240초")
    a_run.add_argument("--workers", type=int, default=6)
    a_run.add_argument("--world", choices=WORLDS, default="unreal", help="unreal = 판정 세계(1차), dense = 빽빽한 숲(2차, 보고만)")
    a_run.add_argument("--name", required=True)
    a_run.add_argument("--out-dir", type=Path, default=OUT)
    a_dense = sub.add_parser("dense")
    a_dense.add_argument("--r5", required=True)
    a_dense.add_argument("--base", required=True)
    a_dense.add_argument("--out", type=Path, default=None)
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("run", "dense"):
        # check·select·judge 는 R4 도구 그대로(같은 규칙). 출력의 'R4' 이름표만 R5 로 읽는다
        if args and args[0] == "judge":
            jp = argparse.ArgumentParser()
            for k in ("--r4", "--base", "--r4-short", "--base-short"):
                jp.add_argument(k, required=True)
            jp.add_argument("--stuck-r4", default=None)
            jp.add_argument("--stuck-base", default=None)
            jp.add_argument("--out", type=Path, default=None)
            ns = jp.parse_args(args[1:])
            res = R4E.judge(R4E.load(ns.r4), R4E.load(ns.base), R4E.load(ns.r4_short), R4E.load(ns.base_short),
                            R4E.load(ns.stuck_r4) if ns.stuck_r4 else None, R4E.load(ns.stuck_base) if ns.stuck_base else None)
            for v in res["criteria"].values():
                if isinstance(v.get("rule"), str):
                    v["rule"] = v["rule"].replace("R4", "R5")
            text = R4E.fmt_judge(res).replace("R4", "R5")
            print(text)
            if ns.out:
                ns.out.write_text(text + "\n", encoding="utf-8")
                ns.out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            return 0 if res["pass"] else 1
        return R4E.main(args)
    a = ap.parse_args(args)
    if a.cmd == "run":
        seeds = rm.parse_seeds(a.seeds)
        res = run(R4E.model_path(a.model), seeds, a.steps, a.workers, a.world)
        a.out_dir.mkdir(parents=True, exist_ok=True)
        out = a.out_dir / f"{a.name}.json"
        out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        p = R4E.pooled(res)
        print(f"{a.name}: 관측 {res['meta']['obs_dim']}·{a.world} 세계 {p['worlds']}개 {res['meta']['wall_s']:.0f}초 · 잡힘 {p['caught']:.4f} "
              f"굶음 {p['starved']:.4f} 산 {p['alive']:.4f} 은신처 안 {p['shelter']:.4f} 도망 {p['beh']['flee']:.4f} 숨기 {p['beh']['hide']:.4f} "
              f"은신처 안 잡힘 {p['catch_cover']} -> {out}")
        return 0
    res = dense_report(R4E.load(a.r5), R4E.load(a.base))
    text = fmt_dense(res)
    print(text)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        a.out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
