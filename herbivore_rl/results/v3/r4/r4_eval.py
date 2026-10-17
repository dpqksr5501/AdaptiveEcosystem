"""v3 R4 판정·점검·고르기 도구 (사전 등록 results/v3/r4/PREREG.md 4~7절). 판정 세계 = 부활 없는 언리얼 거울 configs/v3_wild3_mirror.yaml.

    # herbivore_rl/ 에서
    # 세계 돌리기: 시드마다 지역 셋(메마른 땅·숲·고지 — 그 지역 날씨 + 그 지역 나무 원판)을 하나씩. 두뇌 r1bf = R1b s3 가중치(얼기 막음)
    python results/v3/r4/r4_eval.py run --model r1bf --seeds 32050-32059 --steps 7200 --name early_base
    python results/v3/r4/r4_eval.py run --model ckpt/v3/v3_r4_g995_s0_20m_2m.zip --seeds 32050-32059 --steps 7200 --name early_s0_2m
    # 조기 중단 점검(PREREG 5절): 점검 판 하나를 같은 세계의 R1b-F 판과 견준다
    python results/v3/r4/r4_eval.py check --run results/v3/r4/runs/early_s0_2m.json --base results/v3/r4/runs/early_base.json
    # 게임 모델 고르기(PREREG 6절): 고르기 판들 가운데 잡힌 몫이 가장 낮은 것
    python results/v3/r4/r4_eval.py select --runs results/v3/r4/runs/select_s0.json results/v3/r4/runs/select_s1.json ...
    # 판정(PREREG 4절): 16분·240초 판 넷과 끼임 세기 둘
    python results/v3/r4/r4_eval.py judge --r4 runs/judge_r4_16m.json --base runs/judge_base_16m.json --r4-short runs/judge_r4_240s.json \
        --base-short runs/judge_base_240s.json --stuck-r4 runs/stuck_r4.json --stuck-base runs/stuck_base.json --out judge.md

세계 하나는 거울 실행기(results/v3/mirror/run_mirror.py run_world — 사슴 128, 늑대 4 + 협동, 늑대 식사 5초, 부활 없음)와 같고 진단(--diag 와 같은 칸)을 켠다.
지역 덮기는 짝 비교 실행기와 같은 두 칸이다: features.wild_weather.region = 지역, features.obstacles.fixed = 나무 배치 표(results/v3/wild2/trees/tree_layout.json)의
그 지역 원판. 먹이 지도는 시드의 파이썬 난수 지도다(세 지역이 같은 시드면 같은 먹이 지도에 지역 날씨·나무만 다르다).
시드는 탐색 32000~32099·판정 33000~33099 만 받는다(run_mirror.parse_seeds).
출력 runs/<이름>.json: 메타 + 세계마다 요약(시드·지역·잡힘·굶음·산·은신처 안 사슴-스텝·행동별 산 사슴-스텝·은신처 안 잡힘·사냥).
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
for p in (ROOT, ROOT / "results" / "v3" / "mirror"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

CONFIG = ROOT / "configs" / "v3_wild3_mirror.yaml"
LAYOUT = ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
R1BF = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
OUT = HERE.parent / "runs"
REGIONS = ("Barren", "Forest", "Highland")
BEH = ("graze", "flee", "hide", "freeze", "sleep")
T_CRIT = 1.984                       # 짝 t 양쪽 5%, 자유도 99 (시드 100)
T_REGION = 2.626                     # 지역 기준(G3, 9칸): 짝 t 양쪽 1%, 자유도 99 — 칸이 많아 우연히 걸리는 몫을 줄인다(PREREG 4절)


def region_discs() -> dict:
    d = json.loads(LAYOUT.read_text(encoding="utf-8"))
    return {r["region"]: [[float(v) for v in row] for row in r["discs"]] for r in d["regions"]}


def model_path(text: str) -> Path:
    if text == "r1bf":
        return R1BF
    p = Path(text)
    return p if p.is_absolute() else ROOT / p


def _one(job: dict) -> dict:
    """세계 하나 → 요약(행 줄은 버린다)."""
    import run_mirror as rm

    res = rm.run_world(job)
    m, dg = res["meta"], res["meta"]["diag"]
    cause = np.asarray(m["death_cause"])
    return dict(seed=m["seed"], region=job["region"], n=m["n"], caught=int((cause == 1).sum()), starved=int((cause == 2).sum()),
                alive=int((cause == 0).sum()), shelter_steps=m["shelter_steps"], live_steps=m["live_steps"], beh_steps=dg["beh_steps"],
                catch_cover=dg["catch_cover"], catch_fled=dg["catch_fled"], catches=dg["catches"], starve_fled=dg["starve_fled"],
                hunt=m["hunt"], weather=m.get("weather"), obstacles_n=int(m["obstacles"]["n"]) if "obstacles" in m and "n" in m["obstacles"] else None,
                wall_s=m["wall_s"])


def run(model: Path, seeds, steps: int, workers: int, regions=REGIONS) -> dict:
    import run_mirror as rm
    from env_v2 import rollout as ro

    cfg = rm.mirror_cfg(128, 38, CONFIG)
    if not cfg.v2["features"]["wild_weather"]["enabled"] or cfg.v2["features"]["integrated_stage"]["respawn"]:
        raise ValueError("판정 세계는 날씨를 켜고 부활이 없어야 한다(v3_wild3_mirror.yaml)")
    discs = region_discs()
    base = cfg.to_dict()
    jobs = []
    for s in seeds:
        for r in regions:
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
    meta = dict(config=str(CONFIG.relative_to(ROOT)), config_digest=rm.config_digest(cfg), model=str(Path(model).relative_to(ROOT))
                if Path(model).is_relative_to(ROOT) else str(model), model_sha1=sha, seeds=[int(s) for s in seeds], regions=list(regions),
                steps=int(steps), layout=str(LAYOUT.relative_to(ROOT)), wall_s=round(time.perf_counter() - t0, 1))
    return dict(meta=meta, worlds=worlds)


# --------------------------------------------------------------------- #
# 지표
# --------------------------------------------------------------------- #


def load(path) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() or p.exists() else HERE.parent / p).read_text(encoding="utf-8"))


def per_seed(res: dict, key: str, region: str | None = None) -> dict:
    """시드 → 값(지역 셋 합의 몫, region 을 주면 그 지역만). key ∈ caught·starved·alive(÷ n), shelter(은신처 안 ÷ 산 사슴-스텝)."""
    acc: dict[int, list[float]] = {}
    for w in res["worlds"]:
        if region is not None and w["region"] != region:
            continue
        a = acc.setdefault(int(w["seed"]), [0.0, 0.0])
        if key == "shelter":
            a[0] += w["shelter_steps"]
            a[1] += w["live_steps"]
        else:
            a[0] += w[key]
            a[1] += w["n"]
    return {s: (x / y if y else 0.0) for s, (x, y) in acc.items()}


def paired(a: dict, b: dict) -> dict:
    """같은 시드의 짝 차이 a − b: 평균·표준오차·t·시드 수. 시드 목록이 다르면 멈춘다."""
    if sorted(a) != sorted(b):
        raise ValueError("두 판의 시드가 다르다 — 같은 세계끼리만 견준다")
    keys = sorted(a)
    d = np.array([a[k] - b[k] for k in keys], dtype=np.float64)
    n = len(d)
    m = float(d.mean())
    se = float(d.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    t = m / se if se > 0 else (0.0 if m == 0 else math.copysign(math.inf, m))
    return dict(a=float(np.mean([a[k] for k in keys])), b=float(np.mean([b[k] for k in keys])), diff=m, se=se, t=t, n=n)


def pooled(res: dict) -> dict:
    """판 전체 합: 잡힘·굶음·산 몫, 은신처 안 몫, 행동 몫(산 사슴-스텝), 은신처 안 잡힘 수, 사냥 성공률."""
    W = res["worlds"]
    n = sum(w["n"] for w in W)
    beh = np.sum([w["beh_steps"] for w in W], 0).astype(np.float64)
    live = sum(w["live_steps"] for w in W)
    ends = sum(w["hunt"]["ends"] for w in W)
    succ = sum(w["hunt"]["success"] for w in W)
    return dict(worlds=len(W), caught=sum(w["caught"] for w in W) / n, starved=sum(w["starved"] for w in W) / n,
                alive=sum(w["alive"] for w in W) / n, shelter=sum(w["shelter_steps"] for w in W) / max(live, 1),
                beh={b: float(beh[i] / max(beh.sum(), 1.0)) for i, b in enumerate(BEH)}, catch_cover=int(sum(w["catch_cover"] for w in W)),
                hunt_success=succ / ends if ends else float("nan"), hunt_ends=int(ends))


def check(run_res: dict, base_res: dict) -> dict:
    """조기 중단 점검(PREREG 5절): 점검 판 vs 같은 세계 R1b-F. 멈춤 = 아래 하나라도."""
    a, b = pooled(run_res), pooled(base_res)
    if sorted((w["seed"], w["region"]) for w in run_res["worlds"]) != sorted((w["seed"], w["region"]) for w in base_res["worlds"]):
        raise ValueError("점검 판과 기준 판의 세계가 다르다")
    starve_lim = 1.5 * b["starved"] if b["starved"] > 0 else 0.01
    rules = {
        "flee_half": (a["beh"]["flee"] < 0.5 * b["beh"]["flee"], f"도망 몫 {a['beh']['flee']:.4f} < R1b-F {b['beh']['flee']:.4f} 의 절반"),
        "shelter_3x": (a["shelter"] > 3.0 * b["shelter"], f"은신처 안 몫 {a['shelter']:.4f} > R1b-F {b['shelter']:.4f} 의 3배"),
        "starve_1_5x": (a["starved"] > starve_lim, f"굶은 몫 {a['starved']:.4f} > {starve_lim:.4f} (R1b-F {b['starved']:.4f} 의 1.5배)"),
        "mask_defect": (a["beh"]["freeze"] > 0 or a["beh"]["sleep"] > 0, f"얼기·잠 몫 {a['beh']['freeze']:.4g}·{a['beh']['sleep']:.4g} (0 이어야 한다)"),
    }
    return dict(stop=any(v for v, _ in rules.values()), rules={k: dict(hit=bool(v), text=t) for k, (v, t) in rules.items()}, run=a, base=b)


def judge(r4: dict, base: dict, r4s: dict, bases: dict, stuck_r4: dict | None, stuck_base: dict | None) -> dict:
    """판정(PREREG 4절). 1차 P1 하나가 '나아짐', 나머지 지킴 G1~G6 은 '나빠지지 않음'. 모두 통과해야 R4 성공."""
    out: dict = {"criteria": {}, "report": {}}
    c = out["criteria"]
    p = paired(per_seed(r4, "caught"), per_seed(base, "caught"))
    c["P1_caught_16m"] = dict(p, ok=bool(p["diff"] < 0 and p["t"] <= -T_CRIT), rule="R4 − R1b-F < 0 이고 짝 t ≤ −1.984")
    p = paired(per_seed(r4, "starved"), per_seed(base, "starved"))
    c["G1_starved_16m"] = dict(p, ok=bool(p["t"] < T_CRIT), rule="짝 t < +1.984")
    for tag, a, b in (("16m", r4, base), ("240s", r4s, bases)):
        p = paired(per_seed(a, "alive"), per_seed(b, "alive"))
        c[f"G2_alive_{tag}"] = dict(p, ok=bool(p["t"] > -T_CRIT), rule="짝 t > −1.984")
    for r in REGIONS:
        for key, sign in (("caught", +1), ("starved", +1), ("alive", -1)):
            p = paired(per_seed(r4, key, r), per_seed(base, key, r))
            ok = p["t"] < T_REGION if sign > 0 else p["t"] > -T_REGION
            c[f"G3_{r}_{key}_16m"] = dict(p, ok=bool(ok), rule="짝 t < +2.626" if sign > 0 else "짝 t > −2.626")
    cover = pooled(r4)["catch_cover"] + pooled(r4s)["catch_cover"]
    c["G4_catch_in_shelter"] = dict(value=cover, ok=cover == 0, rule="16분·240초 판정 세계 모두 0")
    if stuck_r4 is not None and stuck_base is not None:
        sd, sw = stuck_counts(stuck_r4), stuck_counts(stuck_base)
        c["G5_stuck"] = dict(r4=sd, base=sw, ok=bool(sd["deer"] == 0 and sd["wolf"] <= sw["wolf"]), rule="사슴 끼임 0, 늑대 끼임 ≤ R1b-F")
    else:
        c["G5_stuck"] = dict(ok=None, rule="끼임 세기 결과가 없다 — 판정 전에 돌린다")
    a, b = pooled(r4), pooled(base)
    use_ok = all(a["beh"][x] > 0.01 for x in ("graze", "flee", "hide"))
    c["G6_no_exploit"] = dict(shelter=a["shelter"], shelter_base=b["shelter"], beh=a["beh"],
                              ok=bool(a["shelter"] <= 2.0 * b["shelter"] and use_ok), rule="은신처 안 몫 ≤ R1b-F 의 2배, 먹기·도망·숨기 모두 1% 넘게")
    out["pass"] = all(v["ok"] for v in c.values() if v["ok"] is not None) and c["G5_stuck"]["ok"] is not None
    rep = out["report"]
    rep["pooled_16m"] = dict(r4=a, base=b)
    rep["pooled_240s"] = dict(r4=pooled(r4s), base=pooled(bases))
    p = paired(per_seed(r4s, "caught"), per_seed(bases, "caught"))
    rep["caught_240s"] = p
    rep["shelter_16m"] = paired(per_seed(r4, "shelter"), per_seed(base, "shelter"))
    return out


def stuck_counts(res: dict) -> dict:
    """stuck_check.py --out JSON → 끼임 수: deer = 사슴 원판 끼임(deer_stuck), wolf = 늑대 원판 끼임(wolf_stuck), wall = 늑대 은신처 둘레 기어감
    (wolf_wall_stuck — 원판 없는 세계에도 있는 늑대 규칙 몫이라 보고만, PREREG 4절 G5)."""
    s = res.get("summary") or {}
    if not all(k in s for k in ("deer_stuck", "wolf_stuck", "wolf_wall_stuck")):
        raise ValueError(f"끼임 결과에서 deer_stuck·wolf_stuck·wolf_wall_stuck 칸을 못 찾았다: {sorted(s)}")
    return dict(deer=int(s["deer_stuck"]), wolf=int(s["wolf_stuck"]), wall=int(s["wolf_wall_stuck"]), worlds=int(s["worlds"]))


def fmt_judge(res: dict) -> str:
    lines = ["| 기준 | R4 | R1b-F | 차이 | t | 규칙 | 통과 |", "|---|---|---|---|---|---|---|"]
    for k, v in res["criteria"].items():
        if "diff" in v:
            lines.append(f"| {k} | {v['a']:.4f} | {v['b']:.4f} | {v['diff']:+.4f} ± {v['se']:.4f} | {v['t']:+.2f} | {v['rule']} | {'예' if v['ok'] else '아니오'} |")
        else:
            val = {x: y for x, y in v.items() if x not in ("ok", "rule")}
            lines.append(f"| {k} | {json.dumps(val, ensure_ascii=False)} | | | | {v['rule']} | {'—' if v['ok'] is None else ('예' if v['ok'] else '아니오')} |")
    lines.append("")
    lines.append(f"**R4 {'성공' if res['pass'] else '실패'}**")
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
    a_run.add_argument("--name", required=True)
    a_run.add_argument("--out-dir", type=Path, default=OUT)
    a_chk = sub.add_parser("check")
    a_chk.add_argument("--run", required=True)
    a_chk.add_argument("--base", required=True)
    a_sel = sub.add_parser("select")
    a_sel.add_argument("--runs", nargs="+", required=True)
    a_sel.add_argument("--base", default=None, help="같은 세계의 R1b-F 판(보고만)")
    a_j = sub.add_parser("judge")
    for k in ("--r4", "--base", "--r4-short", "--base-short"):
        a_j.add_argument(k, required=True)
    a_j.add_argument("--stuck-r4", default=None)
    a_j.add_argument("--stuck-base", default=None)
    a_j.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        seeds = rm.parse_seeds(a.seeds)
        res = run(model_path(a.model), seeds, a.steps, a.workers)
        a.out_dir.mkdir(parents=True, exist_ok=True)
        out = a.out_dir / f"{a.name}.json"
        out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        p = pooled(res)
        print(f"{a.name}: 세계 {p['worlds']}개 {res['meta']['wall_s']:.0f}초 · 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} "
              f"은신처 안 {p['shelter']:.4f} 도망 {p['beh']['flee']:.4f} 숨기 {p['beh']['hide']:.4f} 은신처 안 잡힘 {p['catch_cover']} -> {out}")
        return 0
    if a.cmd == "check":
        r = check(load(a.run), load(a.base))
        for k, v in r["rules"].items():
            print(f"  {k}: {'걸림' if v['hit'] else '-'} ({v['text']})")
        print("멈춤" if r["stop"] else "계속")
        return 0
    if a.cmd == "select":
        rows = []
        for path in a.runs:
            res = load(path)
            p = pooled(res)
            rows.append((p["caught"], p["starved"], path, res["meta"]["model"], p))
        rows.sort(key=lambda x: (x[0], x[1]))
        for c_, s_, path, model, p in rows:
            print(f"  {model}: 잡힘 {c_:.4f} 굶음 {s_:.4f} 산 {p['alive']:.4f} 은신처 안 {p['shelter']:.4f} ({path})")
        if a.base:
            b = pooled(load(a.base))
            print(f"  (R1b-F 같은 세계: 잡힘 {b['caught']:.4f} 굶음 {b['starved']:.4f} 산 {b['alive']:.4f})")
        print(f"고른 모델: {rows[0][3]}")
        return 0
    if a.cmd == "judge":
        res = judge(load(a.r4), load(a.base), load(a.r4_short), load(a.base_short),
                    load(a.stuck_r4) if a.stuck_r4 else None, load(a.stuck_base) if a.stuck_base else None)
        text = fmt_judge(res)
        print(text)
        if a.out:
            a.out.write_text(text + "\n", encoding="utf-8")
            a.out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return 0 if res["pass"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
