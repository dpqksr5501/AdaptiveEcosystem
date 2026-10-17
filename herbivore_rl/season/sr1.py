"""SR1 이어 학습 검정 실행기 (SEASON 5.4, 사전 등록 `results/season/sr1/PREREG.md`).

    python -m season.sr1 --dry-run                          # 1차 선별 잡 목록과 계산 추정만 낸다
    python -m season.sr1                                    # 1차 선별 실행
    python -m season.sr1 --round 2 --pick M2@v20 --dry-run  # 2차 확인 (고른 방식@앵커)
    python -m season.sr1 --verdict                          # 지금까지의 판정으로 통과 규칙(SEASON 5.4:648)을 본다

1차 선별: 시즌 (a) × 방식 {M1, M2, M3(0.1), M3(0.5)} × 앵커 {v1, v20} × 학습 시드 0 = 후보 8개, 그리고 같은 (앵커, 방식,
시드)의 K2-B 8개. M0 은 10-02 측정을 기준으로 쓰고 다시 돌리지 않는다(SEASON 5.4 방식 표).
2차 확인: `--pick 방식@앵커`(예: M2@v20, M3k0.5@v1) 마다 시즌 (a)(b)(c) × 학습 시드 {0, 1}. 이미 있는 후보·K2-B·평가 행은
다시 만들지 않는다. K2-B 는 시즌과 무관하므로 시드마다 하나다.

순서:
1. 앵커 sha1 확인 (`season.common.ANCHOR_SHA1`, #S15 추천값). 다르면 멈춘다.
2. 학습: 후보와 K2-B 를 `python -m season.train_season` 하위 프로세스로 `--parallel` 개씩 돌린다(각 `--threads` 스레드).
   zip 이 이미 있으면 건너뛴다. 기록은 `runs/season/sr1/logs/`.
3. 평가: 워커 풀 하나(`--workers`)로 (시즌, 세계, 앵커 γ)마다 모든 스펙을 한 번에 돈다. 행은 캐시한다
   (`runs/season/cache/eval/`). 앵커·K2-B 행은 후보끼리 함께 쓴다.
4. 판정: 후보마다 A1~A5 (`season.gate.judge`), 통과하면 보류 시드 재확인.
5. 기록: 후보마다 `runs/season/sr1/round<k>/<후보>/gate.json`, 요약 `round<k>.json`·`round<k>.md`. 평가 조건이 사전 등록
   값(시드 20개 × 5000스텝, 학습 2M)이면 요약을 `results/season/sr1/` 에도 쓴다.

계산 추정(`--dry-run`, 10-02 유휴 PC 단가, SEASON 3.2·5.4): 학습은 2M 당 1.0분(0.80~1.01분 측정, 스레드 3)이고
`--parallel` 개씩 묶어 센다. 평가 잡(5000스텝) 하나는 4워커 동시에서 6.85 워커초, 10워커 동시에서 10.8 워커초다. 그
사이 워커 수는 직선으로 잇고 밖은 끝값을 쓴다. 다른 작업이 CPU 를 쓰면 더 걸린다.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import json
import math
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from diagnose_v2 import model_fingerprint
from env_v2.rollout import make_executor, model_gamma
from season.common import (ANCHOR_SHA1, ANCHORS, EVAL_SEEDS, EVAL_STEPS, HOLDOUT_SEEDS, RESULTS, RUNS, SR1_SEEDS,
                           SR1_STEPS, H, method_tag, run_name, sim_digest, train_path)
from season.eval_worlds import (WORLDS, EvalCache, evaluate, gate_bundle, ge_sanity, holdout_bundle, missing_jobs,
                                world_configs)
from season.gate import brief, candidate_ok, clean, gate_a5, holdout, judge, rank_key, sr1_verdict

ROUND1 = {"seasons": ("a",), "methods": (("M1", None), ("M2", None), ("M3", 0.1), ("M3", 0.5)),
          "anchors": ("v1", "v20"), "seeds": (0,)}
ROUND2_SEASONS = ("a", "b", "c")
TRAIN_MIN_PER_2M = 1.0
EVAL_UNIT = ((4, 6.85), (10, 10.8))      # (동시 워커 수, 잡 하나의 워커초), 5000스텝 잡 기준
SR1_DIR = RUNS / "sr1"


@dataclass(frozen=True)
class TrainJob:
    anchor: str                 # v1 | v20
    season: str | None          # a | b | c, K2-B 는 None
    method: str                 # M1 | M2 | M3
    kl: float | None
    seed: int
    steps: int = SR1_STEPS
    root: Path = SR1_DIR        # 산출물 뿌리 (zip 은 <root>/train/)

    @property
    def mtag(self) -> str:
        return method_tag(self.method, self.kl)

    @property
    def name(self) -> str:
        return run_name(self.anchor, self.season, self.mtag, self.seed, self.steps)

    @property
    def path(self) -> Path:
        return train_path(self.anchor, self.season, self.mtag, self.seed, self.steps, root=self.root / "train")

    @property
    def is_k2b(self) -> bool:
        return self.season is None

    def k2b(self) -> "TrainJob":
        return TrainJob(self.anchor, None, self.method, self.kl, self.seed, self.steps, self.root)

    def cmd(self, threads: int) -> list[str]:
        c = [sys.executable, "-m", "season.train_season", "--anchor", self.anchor, "--method", self.method,
             "--seed", str(self.seed), "--steps", str(self.steps), "--threads", str(threads), "--out", str(self.path)]
        c += ["--k2b"] if self.is_k2b else ["--season", self.season]
        if self.kl is not None:
            c += ["--kl-coef", format(self.kl, "g")]
        return c


def parse_pick(tok: str) -> tuple[str, float | None, str]:
    """'M2@v20', 'M3k0.5@v1' → (방식, KL, 앵커)."""
    m, sep, anchor = tok.partition("@")
    if not sep or anchor not in ANCHORS:
        raise SystemExit(f"--pick 은 방식@앵커 꼴이다 (앵커 {list(ANCHORS)}). 받은 값: {tok!r}")
    if m.startswith("M3k"):
        return "M3", float(m[3:].replace("p", ".")), anchor
    if m not in ("M0", "M1", "M2"):
        raise SystemExit(f"--pick 방식은 M0, M1, M2, M3k<계수> 중 하나다. 받은 값: {m!r}")
    return m, None, anchor


def plan(round_no: int, picks: list[str], steps: int, root: Path = SR1_DIR) -> list[TrainJob]:
    """이번 차수의 후보 목록 (K2-B 는 `train_jobs` 가 더한다)."""
    if round_no == 1:
        return [TrainJob(a, s, m, kl, seed, steps, root) for s in ROUND1["seasons"] for a in ROUND1["anchors"]
                for (m, kl) in ROUND1["methods"] for seed in ROUND1["seeds"]]
    if not picks:
        raise SystemExit("2차 확인은 --pick 방식@앵커 가 필요하다 (1차 요약의 '가장 나은 후보'를 보고 고른다)")
    out = []
    for tok in picks:
        m, kl, a = parse_pick(tok)
        out += [TrainJob(a, s, m, kl, seed, steps, root) for s in ROUND2_SEASONS for seed in SR1_SEEDS]
    return out


def train_jobs(cands: list[TrainJob]) -> list[TrainJob]:
    """후보 + 필요한 K2-B (겹침 없이, 순서 유지)."""
    seen, out = set(), []
    for j in cands + [c.k2b() for c in cands]:
        if j not in seen:
            seen.add(j)
            out.append(j)
    return out


# --------------------------------------------------------------------- #
# 계산 추정
# --------------------------------------------------------------------- #


def eval_unit(workers: int) -> float:
    """평가 잡(5000스텝) 하나의 워커초 (10-02 측정 두 점을 직선으로 잇는다)."""
    (w0, u0), (w1, u1) = EVAL_UNIT
    w = min(max(int(workers), w0), w1)
    return u0 + (u1 - u0) * (w - w0) / (w1 - w0)


def estimate(n_train: int, train_steps: int, parallel: int, n_eval: int, eval_steps: int, workers: int) -> dict:
    per_run = TRAIN_MIN_PER_2M * train_steps / SR1_STEPS
    train_min = math.ceil(n_train / max(parallel, 1)) * per_run if n_train else 0.0
    eval_min = n_eval * eval_unit(workers) * (eval_steps / EVAL_STEPS) / max(workers, 1) / 60.0
    return {"train_min": train_min, "eval_min": eval_min, "total_min": train_min + eval_min}


def judge_bundle(c: TrainJob) -> dict:
    """후보의 판정 묶음. SR1 은 현재 = 앵커다."""
    anchor = ANCHORS[c.anchor]
    return gate_bundle(c.path, anchor, c.k2b().path, anchor)


def hold_bundle(c: TrainJob) -> dict:
    return holdout_bundle(c.path, ANCHORS[c.anchor], c.k2b().path)


def eval_specs(cands: list[TrainJob], bundle_fn=judge_bundle) -> dict:
    """{"groups": (시즌, 앵커) → {세계: {스펙 키: 스펙}}, "roles": 후보 → {(세계, 역할): 스펙 키}}.

    스펙 키는 스펙 JSON 이라 여러 후보가 같은 앵커·K2-B 스펙을 함께 쓴다(한 번만 잰다).
    """
    groups: dict[tuple, dict] = {}
    roles: dict[str, dict] = {}
    for c in cands:
        b = bundle_fn(c)
        g = groups.setdefault((c.season, c.anchor), {w: {} for w in WORLDS})
        roles[c.name] = {}
        for w, specs in b.items():
            for role, spec in specs.items():
                key = json.dumps(spec, sort_keys=True)
                g[w][key] = spec
                roles[c.name][(w, role)] = key
    return {"groups": groups, "roles": roles}


def count_eval(cands: list[TrainJob], cache: EvalCache, seeds, steps: int) -> dict:
    es = eval_specs(cands)
    by_world = {w: 0 for w in WORLDS}
    for (season, anchor), worlds in es["groups"].items():
        cfgs = world_configs(season)
        gamma = model_gamma(ANCHORS[anchor])
        for w, specs in worlds.items():
            by_world[w] += missing_jobs(cfgs[w], specs, seeds, steps, gamma, cache)
    hold = set()
    for c in cands:      # 보류 재확인 최대치: 모든 후보가 A1~A5 를 통과할 때
        hold.update({(c.season, c.path), (c.season, ANCHORS[c.anchor]), (c.season, c.k2b().path)})
    return {"by_world": by_world, "total": sum(by_world.values()), "holdout_max": len(hold) * len(HOLDOUT_SEEDS)}


# --------------------------------------------------------------------- #
# 실행
# --------------------------------------------------------------------- #


def check_anchors(tags) -> None:
    for t in sorted(set(tags)):
        sha = model_fingerprint(ANCHORS[t])
        if sha != ANCHOR_SHA1[t]:
            raise SystemExit(f"앵커 {t} ({ANCHORS[t]}) sha1 {sha} 가 기록값 {ANCHOR_SHA1[t]} 과 다르다 (#S15)")


def run_training(jobs: list[TrainJob], parallel: int, threads: int) -> None:
    todo = [j for j in jobs if not j.path.exists()]
    if not todo:
        print("[학습] 할 일 없음 (모두 있다)")
        return
    logs = todo[0].root / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    def one(job: TrainJob) -> tuple[TrainJob, int, float]:
        t0 = time.time()
        with open(logs / f"{job.name}.log", "w", encoding="utf-8") as f:
            rc = subprocess.run(job.cmd(threads), cwd=H, stdout=f, stderr=subprocess.STDOUT).returncode
        return job, rc, time.time() - t0

    print(f"[학습] {len(todo)}개, {parallel}개씩, 스레드 {threads}", flush=True)
    failed = []
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        for job, rc, dt in pool.map(one, todo):
            print(f"  {job.name}: {'완료' if rc == 0 else f'실패 rc={rc}'} ({dt / 60:.1f}분)", flush=True)
            if rc != 0:
                failed.append(job.name)
    if failed:
        raise SystemExit(f"[학습] 실패: {failed} (기록: {logs})")


def run_eval(cands: list[TrainJob], executor, cache: EvalCache, seeds, steps: int, prefix: str = "",
             bundle_fn=judge_bundle) -> dict[str, dict]:
    """후보마다 평가 행 {"<prefix><세계>/<역할>": 행}. 보류 재확인은 bundle_fn=hold_bundle 로 부른다."""
    es = eval_specs(cands, bundle_fn)
    got: dict[tuple, dict] = {}
    for (season, anchor), worlds in es["groups"].items():
        cfgs = world_configs(season)
        gamma = model_gamma(ANCHORS[anchor])
        for w, specs in worlds.items():
            if not specs:
                continue
            t0 = time.time()
            res = evaluate(cfgs[w], specs, seeds, steps, gamma, executor=executor, cache=cache)
            print(f"  [평가] 시즌 {season} · {anchor} · {w}: 스펙 {len(specs)}개 ({time.time() - t0:.0f}초)", flush=True)
            for key, rows in res.items():
                got[(season, anchor, w, key)] = rows
    out = {}
    for c in cands:
        out[c.name] = {f"{prefix}{w}/{role}": got[(c.season, c.anchor, w, key)]
                       for (w, role), key in es["roles"][c.name].items()}
    return out


def train_meta(job: TrainJob) -> dict:
    p = job.path.with_suffix(".json")
    if not p.exists():
        return {}
    m = json.loads(p.read_text(encoding="utf-8"))
    last = (m.get("history") or [{}])[-1]
    return {"elapsed_min": m.get("elapsed_min"), "worlds": m.get("worlds"), "sha1": m.get("out_sha1"),
            "last_rollout": {k: v for k, v in last.items() if k.startswith(("reward_", "anchor_kl"))}}


def md_summary(round_no: int, items: list[dict], meta: dict) -> list[str]:
    def f(x, fmt="+.1%"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    L = [f"# SR1 {round_no}차 요약", "", f"- 생성: {meta['generated']}, 평가 시드 {meta['seeds'][0]}~{meta['seeds'][-1]} × "
         f"{meta['eval_steps']}스텝, 학습 {meta['train_steps']:,}, γ = 앵커 학습 γ", "",
         "| 후보 | A1 | A2 | A3 | A4 | A5 | 보류 | Ge 피식률 vs 현재 (t) | vs K2-B (t) | G G_γ 하락 | B react 비 | B 행동 평균 최대 변화 | 사유 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for it in items:
        r, b = it["result"], it["result"]["brief"]
        ok = {k: "통과" if r[k]["pass"] else "실패" for k in ("A1", "A2", "A3", "A4", "A5")}
        hold = r.get("holdout")
        L.append(f"| {it['name']} | {ok['A1']} | {ok['A2']} | {ok['A3']} | {ok['A4']} | {ok['A5']} | "
                 f"{'—' if hold is None else ('통과' if hold['pass'] else '실패')} | "
                 f"{f(b['ge_pred_rel_vs_cur'])} ({f(b['ge_pred_t_vs_cur'], '+.2f')}) | "
                 f"{f(b['ge_pred_rel_vs_k2b'])} ({f(b['ge_pred_t_vs_k2b'], '+.2f')}) | {f(b['g_gamma_drop'])} | "
                 f"{f(b['b_react_ratio'], '.2f')} | {f(b['b_act_shift_max'], '.3f')} | "
                 f"{', '.join(r['reasons']) or '—'} |")
    L += ["", f"- Ge 덮기 확인(아사 0·번식 0): {'정상' if all(it['result']['ge_sanity']['ok'] for it in items) else '이상'}"]
    best = sorted(items, key=lambda it: rank_key(it["result"]), reverse=True)
    if best:
        L.append("- 가장 나은 후보 순서(전부 통과 > 통과 판정 수 > Ge 피식률 t, 2차 확인 대상 고르기): "
                 + ", ".join(it["name"] for it in best[:3]))
    return L


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SR1 이어 학습 검정 실행기")
    p.add_argument("--round", type=int, choices=(1, 2), default=1)
    p.add_argument("--pick", nargs="*", default=[], help="2차 확인 대상 방식@앵커 (예: M2@v20 M3k0.5@v1)")
    p.add_argument("--dry-run", action="store_true", help="잡 목록과 계산 추정만 낸다")
    p.add_argument("--verdict", action="store_true", help="지금까지의 gate.json 으로 통과 규칙을 본다")
    p.add_argument("--parallel", type=int, default=3, help="동시 학습 수 (SEASON 5.4: 3)")
    p.add_argument("--threads", type=int, default=3, help="학습 하나의 torch 스레드 (SEASON 4.1: 3)")
    p.add_argument("--workers", type=int, default=10, help="평가 워커 수 (SEASON 5.4 단가: 10)")
    p.add_argument("--train-steps", type=int, default=SR1_STEPS)
    p.add_argument("--eval-seeds", type=int, default=len(EVAL_SEEDS), help="사전 등록 20. 줄이면 요약을 results/ 에 쓰지 않는다")
    p.add_argument("--eval-steps", type=int, default=EVAL_STEPS)
    p.add_argument("--root", default=None, help="산출물 뿌리 (기본 runs/season/sr1). 주면 평가 캐시도 그 아래에 두고 "
                                                "요약을 results/ 에 쓰지 않는다")
    args = p.parse_args(argv)
    root = Path(args.root) if args.root else SR1_DIR

    if args.verdict:
        return cmd_verdict(root)

    cands = plan(args.round, args.pick, args.train_steps, root)
    jobs = train_jobs(cands)
    seeds = EVAL_SEEDS[: args.eval_seeds]
    hold_seeds = HOLDOUT_SEEDS[: args.eval_seeds]
    prereg = (args.eval_seeds == len(EVAL_SEEDS) and args.eval_steps == EVAL_STEPS and args.train_steps == SR1_STEPS
              and args.root is None)
    cache = EvalCache(root / "cache") if args.root else EvalCache()
    n_train = sum(not j.path.exists() for j in jobs)
    ev = count_eval(cands, cache, seeds, args.eval_steps)
    est = estimate(n_train, args.train_steps, args.parallel, ev["total"], args.eval_steps, args.workers)
    est_hold = estimate(0, args.train_steps, args.parallel, ev["holdout_max"], args.eval_steps, args.workers)

    print(f"SR1 {args.round}차: 후보 {len(cands)}개, K2-B {len(jobs) - len(cands)}개 (학습 {args.train_steps:,}, "
          f"평가 시드 {len(seeds)} × {args.eval_steps}스텝{'' if prereg else ', 사전 등록 값 아님'})")
    for j in jobs:
        kind = "K2-B" if j.is_k2b else f"시즌 {j.season}"
        shown = j.path.relative_to(H) if j.path.is_relative_to(H) else j.path
        print(f"  {'있음' if j.path.exists() else '새로':4s} {j.name:28s} {kind:6s} → {shown}")
    print(f"평가 잡(캐시 밖): {ev['total']} ({', '.join(f'{w} {n}' for w, n in ev['by_world'].items())}), "
          f"보류 재확인 최대 {ev['holdout_max']}")
    print(f"계산 추정(10-02 유휴 단가): 학습 {n_train}회 ÷ {args.parallel} 동시 → {est['train_min']:.0f}분, "
          f"평가 {ev['total']}잡 ÷ {args.workers}워커 → {est['eval_min']:.0f}분, 합 {est['total_min']:.0f}분 "
          f"(+ 보류 재확인 최대 {est_hold['eval_min']:.0f}분)")
    print(f"코어: 학습 {args.parallel} × {args.threads} 스레드, 평가 {args.workers} 워커 (차례로 돈다)")
    if args.dry_run:
        print("명령 예: " + " ".join(Path(c).name if i == 0 else c for i, c in enumerate(jobs[0].cmd(args.threads))))
        return 0

    check_anchors(j.anchor for j in jobs)
    t0 = time.time()
    run_training(jobs, args.parallel, args.threads)
    ex = make_executor(args.workers)
    try:
        print(f"[평가] 판정 묶음, 워커 {args.workers}", flush=True)
        rows = run_eval(cands, ex, cache, seeds, args.eval_steps)
        items = []
        for c in cands:
            res = judge(rows[c.name], gate_a5(c.path))
            items.append({"name": c.name, "job": c, "result": res})
        passing = [it["job"] for it in items if it["result"]["pass"]]
        if passing:
            print(f"[평가] 보류 재확인 {len(passing)}개", flush=True)
            hold_rows = run_eval(passing, ex, cache, hold_seeds, args.eval_steps, prefix="hold/",
                                 bundle_fn=hold_bundle)
            for it in items:
                if it["name"] in hold_rows:
                    it["result"]["holdout"] = holdout(hold_rows[it["name"]])
    finally:
        if ex is not None:
            ex.shutdown()

    out_dir = root / f"round{args.round}"
    summary = []
    for it in items:
        c, res = it["job"], it["result"]
        res["ge_sanity"] = ge_sanity([v for k, v in rows[c.name].items() if k.startswith("Ge/")])
        res["brief"] = brief(res)
        rec = {"name": c.name, "anchor": c.anchor, "season": c.season, "method": c.mtag, "seed": c.seed,
               "train_steps": c.steps, "prereg": prereg,
               "candidate": str(c.path), "k2b": str(c.k2b().path), "ok": candidate_ok(res),
               "train": train_meta(c), "k2b_train": train_meta(c.k2b())}
        d = out_dir / c.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "gate.json").write_text(json.dumps(clean(dict(rec, result=res)), ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        summary.append(dict(rec, gates={k: res[k]["pass"] for k in ("A1", "A2", "A3", "A4", "A5")},
                            holdout=res.get("holdout", {}).get("pass"), reasons=res["reasons"], brief=res["brief"]))
        print(f"  {c.name}: {'통과' if rec['ok'] else '기각'} {res['reasons']}")
    meta = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "round": args.round,
            "seeds": list(seeds), "eval_steps": args.eval_steps, "train_steps": args.train_steps,
            "prereg": prereg, "elapsed_min": round((time.time() - t0) / 60, 1), "sim_digest": sim_digest(),
            "eval_cache_code": cache.code,
            "command": " ".join(["python", "-m", "season.sr1"] + (sys.argv[1:] if argv is None else list(argv)))}
    doc = {"meta": meta, "candidates": summary}
    lines = md_summary(args.round, items, meta)
    for d in [out_dir.parent] + ([RESULTS / "sr1"] if prereg else []):
        d.mkdir(parents=True, exist_ok=True)
        (d / f"round{args.round}.json").write_text(json.dumps(clean(doc), ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
        (d / f"round{args.round}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


def cmd_verdict(root: Path = SR1_DIR) -> int:
    results = []
    for p in sorted(root.glob("round*/*/gate.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if not d.get("prereg"):              # 사전 등록 조건(2M, 20시드 × 5000스텝)이 아닌 실행은 세지 않는다
            continue
        results.append({k: d[k] for k in ("anchor", "method", "season", "seed", "ok")})
    v = sr1_verdict(results)
    for k, c in v["combos"].items():
        print(f"{k}: 통과 시즌 {c['seasons_passed']} / 본 시즌 {c['seasons_seen']} → {'통과' if c['pass'] else '미통과'}")
    print(f"SR1: {'통과' if v['pass'] else '미통과'} ({v['rule']})")
    d = RESULTS / "sr1" if root == SR1_DIR else root
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.json").write_text(json.dumps(clean(v), ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
