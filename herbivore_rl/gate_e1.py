"""Gate E1 — v2.1 보행·대사의 행동 게이트 (계획서 1-2, 4.4, 5.0, 6.2). 사전 등록: results/v2/e1/PREREG.md

    python gate_e1.py configs --round R0 --run-mult 2 3.625 6 --walk-eat 0.5   # 회차의 팔(배수) 설정 생성
    python gate_e1.py run --round R0 --arm r3_625_ew0_5 --workers 6               # 팔 하나: C2 → C2-seg → 고정 보행 3종 → G_0.998
    python gate_e1.py judge                                                        # 모든 회차 판정표(judge.json·judge.md)

- 10-02 변경(계획서 1-2 행): v2.0b 를 미뤄 v1 먹이(configs/v2_1.yaml 의 v2.0 먹이) 위에서 하고 (d) 는 뺀다.
- 팔 하나 = (뛰기 대사 배수 R, 걷기 섭식 배수 e_walk). 대사식 drain = energy_drain·(c_rest + c_move·(v/herb_speed)²)
  에서 걷기 대사 배수를 1(= v1 대사, 4.4 "평시 에너지 예산을 v1 과 같게")로 묶고 뛰기 배수를 R 로 두면
  c_move = (R − 1)/(1 − 0.4²) = 25(R − 1)/21, c_rest = 1 − 0.4²·c_move = (21 − 4(R − 1))/21 이다. R = 3.625 가
  제안값(c_rest 0.5, c_move 3.125, 계획서의 "약 3.6")이다. 정지 대사 배수는 c_rest 라 R 이 클수록 정지가 싸진다.
- 계산은 모두 `diagnose_v2.py constsearch` 가 한다(이 파일은 명령을 만들어 부르고 결과 JSON 을 판정한다). 실행한
  명령 전문은 팔마다 `run.json` 에 남는다. 판정 규칙은 PREREG.md 와 같고, 어긋나면 PREREG.md 가 기준이다.
- 판정에 쓰는 값은 평가 시드 10000~10019 × 5000스텝, 결정적 상수 정책, γ_train = configs/ppo_best.yaml 의 γ
  (0.9916661555611042, 계획서의 0.9917, 10절 #27), 끝 600스텝 제외. G_0.998(10000스텝, 앞 500·끝 2500 제외)은 보고만
  한다(5.0). 출력은 results/v2/e1/ 아래다. 기존 결과·캐시를 덮지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "v2" / "e1"
BASE_CONFIG = ROOT / "configs" / "v2_1.yaml"

ROUNDS = ("R0", "R1", "R2")               # R0 = 제안값과 배수 훑기, R1·R2 = 보정 1·2회차 (5.0 최대 2회)
ROUND_LABEL = {"R0": "R0 제안값·배수 훑기", "R1": "R1 보정 1회차", "R2": "R2 보정 2회차"}

# 4.4 표의 걷기 속력(× herb_speed). 걷기 대사 배수 = c_rest + c_move·WALK_SPEED² 를 1 로 묶는다.
WALK_SPEED = 0.4
PROPOSAL_R = 3.625                        # c_rest 0.5, c_move 3.125 (계획서 4.4 제안값, "약 3.6")
R0_RUN_MULTS = (2.0, PROPOSAL_R, 6.0)     # 계획서 1-2 "뛰기 배수 {2, 3.6, 6}"
R0_WALK_EAT = 0.5                         # 4.4 표 걷기 섭식 배수
EAT_STOP, EAT_RUN = 1.0, 0.0              # 정지·뛰기 섭식 배수는 보정하지 않는다(PREREG 4절)
WALK_EAT_UP = (0.5, 0.75, 1.0)            # 보정 사다리 (PREREG 4절)
WALK_EAT_DOWN = (0.5, 0.35, 0.25)
COMMON_ONLY_RUN_MULTS = (1.5, 2.5, 4.5)   # 공통 규칙만 실패할 때 다음 회차의 배수 (PREREG 4절)

# C2 탐색 시작점(PREREG 2절): v1 최적 상수(계획서 2.1, Optuna 112회)에 보행 3단의 가운데 값, 그리고 v1 학습 전 최고 상수
# + 걷기(diagnose_v2 기본 enqueue 와 같다). 정지 상수끼리는 조향 값과 무관하게 G 가 같아서, 같은 점수일 때 앞 trial 이
# 뽑히는 순서 덕에 정지가 최적이면 v1 C2 조향이 바탕이 된다.
V1_C2 = (0.4207, 0.8656, 0.1054, 0.0044)
V1_PRETRAIN_BEST = (0.39, 0.99, 0.92, 0.15)
GAIT_CENTERS = (0.1667, 0.5, 0.8333)
C2_ENQUEUE = tuple(V1_C2 + (s,) for s in GAIT_CENTERS) + (V1_PRETRAIN_BEST + (0.5,),)

# C2-seg 구간(계획서 1-2): (포식자 보임 & d_pred < 0.5·see_r) × (energy < 0.5 / ≥ 0.5). 관측 2 = d_pred/see_r(안 보이면 1)
# 이라 "보임 & d < 0.5·see_r" ⇔ 관측 2 < 0.5. 구간 id = 2·[관측 2 ≥ 0.5] + [energy ≥ 0.5] (env_v2/rollout.segment_ids).
SEG_BINS = ("2:0.5", "4:0.5")
SEG_DIMS = ("speed",)
SEGMENT_LABEL = ("가까움·배고픔", "가까움·배부름", "멂/안 보임·배고픔", "멂/안 보임·배부름")
FIXED_GAITS = (("stop", 0.0), ("walk", 0.5), ("run", 1.0))   # 고정 보행 3종의 speed 값(C2 조향 그대로)
GAIT_NAME = ("정지", "걷기", "뛰기")

# 판정 기준 (계획서 1-2, PREREG 3절)
T_CRIT = 2.093                            # 평가 시드 20개 짝지은 t, 자유도 19, 양측 5%
CRIT = dict(starve_lo=0.10, starve_hi=0.30, hungry_min=0.15, walk_min=0.20)
CRITERIA = ("common", "a", "b", "c")


# --------------------------------------------------------------------- #
# 팔(배수) 설정
# --------------------------------------------------------------------- #


def metabolism(run_mult: float) -> tuple[float, float]:
    """뛰기 대사 배수 R → (c_rest, c_move). 걷기 배수 = c_rest + 0.4²·c_move = 1 로 묶는다.

    0.4² = 4/25 를 분수로 써서 R = 3.625 가 제안값 (0.5, 3.125) 과 비트 단위로 같게 한다.
    R 은 (1, 6.25] 이어야 한다(c_move > 0, c_rest ≥ 0).
    """
    r = float(run_mult)
    if not 1.0 < r <= 1.0 + 21.0 / 4.0:
        raise ValueError(f"뛰기 배수 R 은 (1, 6.25] 안이어야 한다(걷기 배수 1 고정). 받은 값: {r}")
    return (21.0 - 4.0 * (r - 1.0)) / 21.0, 25.0 * (r - 1.0) / 21.0


def arm_name(run_mult: float, walk_eat: float) -> str:
    return f"r{float(run_mult):g}_ew{float(walk_eat):g}".replace(".", "_")


def arm_config(run_mult: float, walk_eat: float, base: Path = BASE_CONFIG) -> dict:
    """configs/v2_1.yaml 에서 speed 의 c_rest·c_move·gait_eat 만 바꾼 설정 dict."""
    with open(base, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    c_rest, c_move = metabolism(run_mult)
    sp = d["features"]["speed"]
    sp["c_rest"], sp["c_move"] = c_rest, c_move
    sp["gait_eat"] = [EAT_STOP, float(walk_eat), EAT_RUN]
    return d


def write_arm_config(rnd: str, run_mult: float, walk_eat: float, out: Path | None = None) -> Path:
    out = OUT if out is None else out
    d = arm_config(run_mult, walk_eat)
    c_rest, c_move = metabolism(run_mult)
    sp = d["features"]["speed"]
    mult = [c_rest + c_move * s * s for s in sp["gait_speed"]]
    head = [
        f"# Gate E1 {rnd} 팔 {arm_name(run_mult, walk_eat)} — gate_e1.py configs 가 configs/v2_1.yaml 에서 만들었다. 손으로 고치지 않는다.",
        f"# 바꾼 계수(그 밖은 configs/v2_1.yaml 과 같다): 뛰기 대사 배수 R = {run_mult:g} (걷기 배수 1 고정) →",
        f"#   c_rest = (21 − 4(R − 1))/21 = {c_rest!r}, c_move = 25(R − 1)/21 = {c_move!r}",
        f"#   대사 배수 [정지, 걷기, 뛰기] = [{', '.join(f'{m:.4f}' for m in mult)}], 걷기 섭식 배수 e_walk = {walk_eat:g}",
        "",
    ]
    path = out / "configs" / f"{rnd}_{arm_name(run_mult, walk_eat)}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(head) + yaml.safe_dump(d, sort_keys=False, allow_unicode=True), encoding="utf-8")
    from env_v2.config import load_v2_config      # 읽혀야 한다(형식 검사)
    from env_v2.world import _speed_params
    p = _speed_params(load_v2_config(path).v2["features"]["speed"])
    assert abs(p["drain_mult"][1] - 1.0) < 1e-12 and abs(p["drain_mult"][2] - run_mult) < 1e-12, p
    return path


# --------------------------------------------------------------------- #
# 팔 하나 실행 (diagnose_v2 constsearch 를 부른다)
# --------------------------------------------------------------------- #


def arm_dir(rnd: str, arm: str, out: Path | None = None) -> Path:
    return (OUT if out is None else out) / rnd / arm


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _fmt(x: float) -> str:
    return repr(float(x))


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# 도구 시험(--smoke)용 작은 조건. 판정 실행에는 쓰지 않는다(run.json 에 smoke 로 남는다).
SMOKE_SEARCH = ["--trials", "3", "--top-k", "2", "--search-seeds", "0:1", "--search-steps", "700",
                "--rescore-seeds", "100:101", "--rescore-steps", "700"]
SMOKE_EVAL = ["--eval-seeds", "10000:10002", "--eval-steps", "1300"]


def commands_for(cfg: Path, d: Path, workers: int, c2_best=None, seg_table=None,
                 smoke: bool = False) -> list[tuple[str, list[str]]]:
    """팔 하나의 단계별 diagnose_v2 인자. 앞 단계 결과(C2 best, C2-seg 표)가 있어야 뒤 단계 인자가 정해진다.

    판정 실행은 탐색·재측정·평가 조건을 diagnose_v2 기본값(PREREG 2절)으로 둔다. `smoke` 는 도구 시험용이다.
    """
    common = ["--config", rel(cfg), "--workers", str(workers)]
    search = SMOKE_SEARCH + SMOKE_EVAL if smoke else []
    ev = SMOKE_EVAL if smoke else []
    steps: list[tuple[str, list[str]]] = []
    enq = []
    for v in C2_ENQUEUE:
        enq += ["--enqueue"] + [_fmt(x) for x in v]
    steps.append(("constsearch", ["constsearch", *common, "--out", rel(d), *enq, *search]))
    steps.append(("constsearch_seg", ["constsearch", *common, "--out", rel(d), "--seg-bins", *SEG_BINS,
                                      "--seg-dims", *SEG_DIMS, *search]))
    if c2_best is not None:
        for name, s in FIXED_GAITS:
            steps.append((f"fixed_{name}", ["constsearch", *common, "--out", rel(d), "--tag", f"fixed_{name}",
                                            "--const-action", *[_fmt(x) for x in list(c2_best)[:4]], _fmt(s),
                                            *ev]))
        if seg_table is not None:
            steps.append(("g998/c2seg_g998", [
                "constsearch", *common, "--out", rel(d / "g998"), "--tag", "c2seg_g998", "--g998",
                "--seg-bins", *SEG_BINS, "--seg-dims", *SEG_DIMS,
                "--base-action", *[_fmt(x) for x in c2_best],
                "--const-action", *[_fmt(x) for x in seg_table], *(ev[:2] if smoke else [])]))
    return steps


def cmd_run(args) -> int:
    out = Path(args.out) if args.out else OUT
    cfg = out / "configs" / f"{args.round}_{args.arm}.yaml"
    if not cfg.exists():
        raise SystemExit(f"{rel(cfg)} 가 없다. 먼저 gate_e1.py configs --round {args.round} ... 로 만든다")
    from diagnose_v2 import config_digest
    from env_v2.config import load_v2_config
    digest = config_digest(load_v2_config(cfg))
    d = arm_dir(args.round, args.arm, out)
    d.mkdir(parents=True, exist_ok=True)
    log = d / "run.log"
    record = load_json(d / "run.json") or {"round": args.round, "arm": args.arm, "config": rel(cfg),
                                            "config_digest": digest, "smoke": bool(args.smoke), "steps": []}
    if bool(record.get("smoke")) != bool(args.smoke):
        raise SystemExit(f"{rel(d)} 는 {'도구 시험' if record.get('smoke') else '판정'} 실행 기록이다. 섞지 않는다")
    if record.get("config_digest") != digest:
        raise SystemExit(f"{rel(d)} 는 다른 설정({record.get('config_digest')})으로 잰 팔이다. 덮지 않는다")
    done = {s["stem"] for s in record["steps"] if s.get("returncode") == 0}
    while True:
        c2 = load_json(d / "constsearch.json")
        seg = load_json(d / "constsearch_seg.json")
        steps = commands_for(cfg, d, args.workers, c2 and c2["best"], seg and seg["best"], smoke=args.smoke)
        todo = [(stem, a) for stem, a in steps if stem not in done]
        if not todo:
            break
        stem, a = todo[0]
        res = d / f"{stem}.json"
        prev = load_json(res)
        if prev is not None:
            if prev.get("meta", {}).get("config_digest") != digest:
                raise SystemExit(f"{rel(res)} 는 다른 설정의 결과다. 덮지 않는다")
            raise SystemExit(f"{rel(res)} 가 이미 있는데 run.json 에 기록이 없다. 확인 뒤 지우고 다시 돌린다")
        cmd = [sys.executable, "-u", "diagnose_v2.py", *a]
        line = "python diagnose_v2.py " + " ".join(a)
        print(f"[{args.round}/{args.arm}] {line}", flush=True)
        t0 = time.time()
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n$ {line}\n")
            f.flush()
            rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        record["steps"].append({"stem": stem, "command": line, "returncode": rc,
                                "elapsed_s": round(time.time() - t0, 1),
                                "finished": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        record["python"] = platform.python_version()
        (d / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        if rc != 0:
            raise SystemExit(f"실패 (종료 코드 {rc}): {line}. 로그 {rel(log)}")
        done.add(stem)
    print(f"[{args.round}/{args.arm}] 끝", flush=True)
    return 0


def cmd_configs(args) -> int:
    out = Path(args.out) if args.out else OUT
    for r in args.run_mult:
        for e in args.walk_eat:
            p = write_arm_config(args.round, r, e, out)
            print(f"{rel(p)}  (arm {arm_name(r, e)})")
    return 0


# --------------------------------------------------------------------- #
# 판정 (순수 함수 — tests/test_gate_e1.py)
# --------------------------------------------------------------------- #


def gait_of(value: float, thresholds) -> int:
    """speed 행동값 → 보행 (env_v2/world.py `_gait_step` 1a 와 같은 문턱): 0 정지, 1 걷기, 2 뛰기."""
    t_walk, t_run = thresholds
    return int(value >= t_walk) + int(value >= t_run)


def _f(v) -> float:
    """JSON 값 → float. diagnose_v2 는 nan·inf 를 null 로 쓴다."""
    return float("nan") if v is None else float(v)


def _m(d: dict, col: str) -> float:
    return _f(d["eval"]["mean"].get(col))


def _paired(a, b) -> dict:
    """평가 시드를 짝지은 t (diagnose_v2.paired 와 같은 식). a − b."""
    import numpy as np

    from diagnose_v2 import paired
    return paired(np.asarray(a, dtype=float), np.asarray(b, dtype=float))


def judge_arm(c2: dict, seg: dict, fixed: dict[str, dict], g998: dict | None, thresholds) -> dict:
    """팔 하나의 판정 (PREREG 3절). 입력은 diagnose_v2 constsearch 결과 JSON 이다."""
    nan = float("nan")
    seeds = [r["seed"] for r in seg["per_seed"]["C2-seg"]]
    for name, d in [("C2", c2), *fixed.items()]:
        got = [r["seed"] for r in d["per_seed"]["C2"]]
        if got != seeds:
            raise ValueError(f"{name} 의 평가 시드가 C2-seg 와 다르다: {got[:3]} vs {seeds[:3]}")
    if [float(x) for x in seg["base_action"]] != [float(x) for x in c2["best"]]:
        raise ValueError("C2-seg 의 바탕 상수가 이 팔의 C2 best 와 다르다")
    t = {k: _f(seg["eval"]["vs_C2"]["g_gamma"].get(k)) for k in ("diff", "t")}
    table = [float(r[0]) for r in seg["best_table"]]
    gaits = [gait_of(v, thresholds) for v in table]
    common = dict(diff=t["diff"], t=t["t"], higher=bool(t["diff"] > 0 and math.isfinite(t["t"]) and t["t"] > T_CRIT),
                  table=table, gaits=gaits, distinct=len(set(gaits)) >= 2)
    common["pass"] = common["higher"] and common["distinct"]
    share, hungry = _m(seg, "starve_share"), _m(seg, "hungry_frac")
    a = dict(starve_share=share, hungry_frac=hungry,
             pass_=bool(CRIT["starve_lo"] <= share <= CRIT["starve_hi"] and hungry >= CRIT["hungry_min"]),
             low=bool(share < CRIT["starve_lo"] or hungry < CRIT["hungry_min"]), high=bool(share > CRIT["starve_hi"]))
    walk = _m(seg, "walk_frac")
    b = dict(walk_frac=walk, walk_frac_cmd=_m(seg, "walk_frac_cmd"), pass_=bool(walk > CRIT["walk_min"]))
    sw, sr = fixed["walk"], fixed["run"]
    tt = _paired([r["starve_rate"] for r in sw["per_seed"]["C2"]], [r["starve_rate"] for r in sr["per_seed"]["C2"]])
    c = dict(starve_rate_walk=_m(sw, "starve_rate"), starve_rate_run=_m(sr, "starve_rate"), t=_f(tt["t"]),
             pass_=bool(_m(sw, "starve_rate") < _m(sr, "starve_rate")))
    out = dict(common=common, a=a, b=b, c=c)
    out["passed"] = {"common": common["pass"], "a": a["pass_"], "b": b["pass_"], "c": c["pass_"]}
    out["pass"] = all(out["passed"].values())
    out["n_pass"] = sum(out["passed"].values())
    out["c2"] = dict(best=c2["best"], gait=gait_of(c2["best"][-1], thresholds),
                     **{k: _m(c2, k) for k in ("g_gamma", "mean_return", "survival", "repro", "predation_rate",
                                                "starve_rate", "starve_share", "hungry_frac", "walk_frac",
                                                "stop_frac", "run_frac")})
    out["seg"] = {k: _m(seg, k) for k in ("g_gamma", "mean_return", "survival", "repro", "predation_rate",
                                          "starve_rate", "starve_share", "hungry_frac", "walk_frac", "stop_frac",
                                          "run_frac", "stall_frac", "b1", "b2", "b8", "b8_cmd", "p_run_unseen",
                                          "p_run_d025", "p_run_d050", "p_run_d100", "p_stop_hungry",
                                          "p_stop_full")}
    out["fixed"] = {n: {k: _m(d, k) for k in ("g_gamma", "survival", "repro", "predation_rate", "starve_rate",
                                              "starve_share", "hungry_frac")} for n, d in fixed.items()}
    if g998 is not None:
        g = {k: _f(g998["eval"]["vs_C2"]["g_gamma"].get(k)) for k in ("diff", "t")}
        out["g998"] = dict(seg=_m(g998, "g_gamma"), c2=_f(g998["ref_mean"]["C2"]["g_gamma"]), diff=g["diff"], t=g["t"],
                           higher=bool(g["diff"] > 0 and math.isfinite(g["t"]) and g["t"] > T_CRIT))
        # 5.0 "0.998 에서만 통과" 후보: γ_train 공통 규칙만 G 때문에 실패하고 G_0.998 로는 높고 나머지는 통과
        out["g998_only"] = bool(not common["higher"] and out["g998"]["higher"] and common["distinct"]
                                and a["pass_"] and b["pass_"] and c["pass_"])
    else:
        out["g998"], out["g998_only"] = None, False
    return out


def select_arm(arms: dict[str, dict]) -> str | None:
    """회차 안 선택 (PREREG 3.5): 통과한 팔 가운데 제안 배수(R 3.625)를 먼저, 아니면 공통 규칙 t 가 큰 팔."""
    ok = {k: v for k, v in arms.items() if v["judge"]["pass"]}
    if not ok:
        return None
    prop = [k for k, v in ok.items() if v["run_mult"] == PROPOSAL_R]
    if prop:
        return prop[0]
    return max(ok, key=lambda k: ok[k]["judge"]["common"]["t"])


def closest_arm(arms: dict[str, dict]) -> str:
    """보정 기준 팔 (PREREG 4절): 통과 항목 수가 가장 많은 팔. 같으면 제안 배수, 그다음 공통 규칙 t 가 큰 팔."""
    def key(k):
        v = arms[k]
        t = v["judge"]["common"]["t"]
        return (v["judge"]["n_pass"], v["run_mult"] == PROPOSAL_R, t if math.isfinite(t) else -math.inf)
    return max(arms, key=key)


def _step(ladder, e: float) -> float | None:
    i = [round(x, 6) for x in ladder].index(round(e, 6)) if round(e, 6) in [round(x, 6) for x in ladder] else None
    if i is None or i + 1 >= len(ladder):
        return None
    return ladder[i + 1]


def next_round(history: list[dict]) -> dict:
    """앞 회차 판정 → 다음 회차 계수 (PREREG 4절의 기계적 규칙). history = 회차 순서의 판정 dict 목록.

    반환: {"action": "pass" | "calibrate" | "stop", "run_mults": [...], "walk_eat": e, "reason": "..."}.
    """
    last = history[-1]
    if last.get("selected"):
        return {"action": "pass", "reason": f"{last['round']} 에서 {last['selected']} 통과"}
    if len(history) >= len(ROUNDS):
        return {"action": "stop", "reason": "보정 2회 뒤에도 통과한 팔이 없다(5.0). 멈추고 보고한다"}
    if any(v["judge"].get("g998_only") for v in last["arms"].values()):
        return {"action": "stop", "reason": "γ_train 은 실패, G_0.998 로만 공통 규칙 통과인 팔이 있다 — PREREG 3.6 의 "
                                            "0.998 재탐색을 먼저 한다(보정 회차를 쓰지 않는다)"}
    k = last["closest"]
    arm = last["arms"][k]
    j = arm["judge"]
    e = float(arm["walk_eat"])
    if not j["passed"]["c"]:
        return {"action": "stop", "reason": f"{k}: (c) 실패는 구현 확인 대상이다(구성상 성립해야 한다). 보정하지 않는다"}
    prev_dir = last.get("direction")
    if not j["passed"]["b"] or j["a"]["high"]:
        direction, why = "up", ("(b) 걷기 ≤ 20%" if not j["passed"]["b"] else "(a) 아사 비중 > 30%")
    elif j["a"]["low"]:
        direction, why = "down", "(a) 아사 비중 < 10% 또는 energy<0.5 < 15%"
    else:
        # 남은 실패는 공통 규칙뿐이다
        return _not_repeated(history, {
            "action": "calibrate", "run_mults": list(COMMON_ONLY_RUN_MULTS), "walk_eat": e, "direction": None,
            "basis": k, "reason": f"{k}: 공통 규칙만 실패 → e_walk {e:g} 그대로, 배수를 {list(COMMON_ONLY_RUN_MULTS)} 로"})
    if prev_dir and prev_dir != direction:
        e_prev = float(history[-2]["walk_eat"])
        new = round((e + e_prev) / 2.0, 6)
        how = f"방향이 바뀌어 앞 두 값 {e_prev:g}·{e:g} 의 가운데"
    else:
        new = _step(WALK_EAT_UP if direction == "up" else WALK_EAT_DOWN, e)
        how = f"사다리 {'↑' if direction == 'up' else '↓'}"
    if new is None:
        return {"action": "stop", "reason": f"{k}: {why} 인데 e_walk {e:g} 에서 사다리 끝이다. 멈추고 보고한다"}
    return _not_repeated(history, {
        "action": "calibrate", "run_mults": list(R0_RUN_MULTS), "walk_eat": new, "direction": direction,
        "basis": k, "reason": f"{k}: {why} → e_walk {e:g} → {new:g} ({how}), 배수 {list(R0_RUN_MULTS)}"})


def _arm_set(r: dict) -> tuple:
    return tuple(sorted((round(float(v["run_mult"]), 6), round(float(v["walk_eat"]), 6)) for v in r["arms"].values()))


def _not_repeated(history: list[dict], nxt: dict) -> dict:
    """다음 회차가 이미 돌린 회차와 같은 계수면 멈춘다(결정적이라 같은 결과가 나온다. PREREG 변경 기록 10-02)."""
    want = tuple(sorted((round(float(r), 6), round(float(nxt["walk_eat"]), 6)) for r in nxt["run_mults"]))
    for r in history:
        if _arm_set(r) == want:
            return {"action": "stop", "reason": f"{nxt['reason']} — 그런데 {r['round']} 와 같은 계수라 다시 돌려도 같은 "
                                                "결과다. 멈추고 보고한다"}
    return nxt


def load_round(rnd: str, out: Path | None = None) -> dict | None:
    """회차 디렉터리의 팔들을 읽어 판정한다. 끝나지 않은 팔(결과 JSON 이 모자람)은 incomplete 로 둔다."""
    out = OUT if out is None else out
    base = out / rnd
    cfgs = sorted((out / "configs").glob(f"{rnd}_*.yaml"))
    if not cfgs:
        return None
    from env_v2.config import load_v2_config
    from env_v2.world import _speed_params
    arms, incomplete = {}, []
    walk_eats = set()
    for cfg in cfgs:
        arm = cfg.stem[len(rnd) + 1:]
        p = _speed_params(load_v2_config(cfg).v2["features"]["speed"])
        d = base / arm
        c2, seg = load_json(d / "constsearch.json"), load_json(d / "constsearch_seg.json")
        fixed = {n: load_json(d / f"fixed_{n}.json") for n, _ in FIXED_GAITS}
        g998 = load_json(d / "g998" / "c2seg_g998.json")
        info = dict(config=rel(cfg), run_mult=round(float(p["drain_mult"][2]), 6),
                    walk_eat=float(p["eat"][1]), drain_mult=[float(x) for x in p["drain_mult"]],
                    c_rest=p["c_rest"], c_move=p["c_move"])
        walk_eats.add(info["walk_eat"])
        if c2 is None or seg is None or any(v is None for v in fixed.values()):
            incomplete.append(arm)
            continue
        info["judge"] = judge_arm(c2, seg, fixed, g998, p["thresholds"])
        info["seg_labels"] = seg.get("segments")
        rj = load_json(d / "run.json") or {}
        info["commands"] = [s["command"] for s in rj.get("steps", [])]
        info["elapsed_s"] = sum(s.get("elapsed_s", 0) for s in rj.get("steps", []))
        arms[arm] = info
    res = dict(round=rnd, arms=arms, incomplete=incomplete,
               walk_eat=walk_eats.pop() if len(walk_eats) == 1 else None)
    if arms and not incomplete:
        res["selected"] = select_arm(arms)
        res["closest"] = closest_arm(arms)
    return res


# --------------------------------------------------------------------- #
# 판정표
# --------------------------------------------------------------------- #


def f3(x, nd=3) -> str:
    return "—" if x is None or not math.isfinite(float(x)) else f"{float(x):.{nd}f}"


def ok(b) -> str:
    return "통과" if b else "실패"


def md_round(r: dict) -> list[str]:
    L = [f"## {ROUND_LABEL.get(r['round'], r['round'])}", ""]
    if r["incomplete"]:
        L += [f"- 끝나지 않은 팔: {', '.join(r['incomplete'])}", ""]
    if not r["arms"]:
        return L
    L += ["| 팔 | R (뛰기 배수) | 대사 배수 [정지, 걷기, 뛰기] | e_walk | C2 보행 | C2-seg 구간별 speed (보행) | "
          "G_γ C2 → C2-seg (Δ, t) | 공통 | 아사 비중 | energy<0.5 | (a) | 걷기 | (b) | 아사율 걷기 / 뛰기 | (c) | "
          "G_0.998 Δ (t) | 판정 |",
          "|---" * 17 + "|"]
    for k, v in r["arms"].items():
        j = v["judge"]
        cm = j["common"]
        segs = ", ".join(f"{x:.3f}({GAIT_NAME[g]})" for x, g in zip(cm["table"], cm["gaits"]))
        g9 = j.get("g998")
        g9s = "—" if not g9 else f"{g9['diff']:+.3f} ({g9['t']:+.2f})"
        L.append(
            f"| {k} | {v['run_mult']:g} | [{', '.join(f'{m:.3f}' for m in v['drain_mult'])}] | {v['walk_eat']:g} | "
            f"{GAIT_NAME[j['c2']['gait']]} ({j['c2']['best'][-1]:.3f}) | {segs} | "
            f"{f3(j['c2']['g_gamma'])} → {f3(j['seg']['g_gamma'])} ({cm['diff']:+.3f}, {cm['t']:+.2f}) | "
            f"{ok(cm['pass'])}{'' if cm['distinct'] else ' (보행 같음)'} | {f3(j['a']['starve_share'])} | "
            f"{f3(j['a']['hungry_frac'])} | {ok(j['a']['pass_'])} | {f3(j['b']['walk_frac'])} | {ok(j['b']['pass_'])} | "
            f"{f3(j['c']['starve_rate_walk'], 5)} / {f3(j['c']['starve_rate_run'], 5)} | {ok(j['c']['pass_'])} | "
            f"{g9s} | **{'PASS' if j['pass'] else 'FAIL'}** |")
    L += ["", "구간 순서: " + ", ".join(f"s{i} {lab}" for i, lab in enumerate(SEGMENT_LABEL)), ""]
    L += ["### 보조 지표 (판정 아님: C2-seg 의 결과·행동, 6.2 B1·B2·B8)", "",
          "| 팔 | 수명 C2 / C2-seg | 피식률 C2 / C2-seg | 번식 C2 / C2-seg | 정지 / 걷기 / 뛰기 | B1 | B2 | B8 (/초) |",
          "|---" * 8 + "|"]
    for k, v in r["arms"].items():
        j = v["judge"]
        s, c = j["seg"], j["c2"]
        L.append(f"| {k} | {f3(c['survival'], 1)} / {f3(s['survival'], 1)} | {f3(c['predation_rate'], 5)} / "
                 f"{f3(s['predation_rate'], 5)} | {f3(c['repro'], 2)} / {f3(s['repro'], 2)} | {f3(s['stop_frac'])} / "
                 f"{f3(s['walk_frac'])} / {f3(s['run_frac'])} | {f3(s['b1'])} | {f3(s['b2'])} | {f3(s['b8'])} |")
    L += ["", "### 고정 보행 3종 (C2 조향 그대로, speed 만 고정)", "",
          "| 팔 | 보행 | G_γ | 수명 | 번식 | 피식률 | 아사율 | 아사 비중 | energy<0.5 |", "|---" * 9 + "|"]
    for k, v in r["arms"].items():
        for n, _ in FIXED_GAITS:
            m = v["judge"]["fixed"][n]
            L.append(f"| {k} | {GAIT_NAME[[g for g, _ in FIXED_GAITS].index(n)]} | {f3(m['g_gamma'])} | "
                     f"{f3(m['survival'], 1)} | {f3(m['repro'], 2)} | {f3(m['predation_rate'], 5)} | "
                     f"{f3(m['starve_rate'], 5)} | {f3(m['starve_share'])} | {f3(m['hungry_frac'])} |")
    L.append("")
    if "selected" in r:
        L.append(f"- 회차 선택: {r['selected'] or '없음 (통과한 팔 없음)'}. 보정 기준 팔(통과 항목 최다): {r['closest']}")
    return L


def cmd_judge(args) -> int:
    out = Path(args.out) if args.out else OUT
    history, rounds = [], {}
    for rnd in ROUNDS:
        r = load_round(rnd, out)
        if r is None:
            break
        rounds[rnd] = r
        if r["incomplete"] or not r["arms"]:
            break
        if history:
            r["direction"] = history[-1].get("next", {}).get("direction")
        history.append(r)
        r["next"] = next_round(history)
        if r["next"]["action"] != "calibrate":
            break
    final = None
    if history and not history[-1]["incomplete"]:
        nx = history[-1]["next"]
        if nx["action"] == "pass":
            last = history[-1]
            arm = last["arms"][last["selected"]]
            final = dict(verdict="PASS", round=last["round"], arm=last["selected"], run_mult=arm["run_mult"],
                         walk_eat=arm["walk_eat"], c_rest=arm["c_rest"], c_move=arm["c_move"],
                         drain_mult=arm["drain_mult"], c2=arm["judge"]["c2"]["best"],
                         seg_table=arm["judge"]["common"]["table"])
        elif nx["action"] == "stop":
            final = dict(verdict="FAIL", round=history[-1]["round"], reason=nx["reason"])
    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "criteria": CRIT, "t_crit": T_CRIT, "rounds": rounds, "final": final}
    out.mkdir(parents=True, exist_ok=True)
    (out / "judge.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    L = ["# Gate E1 판정표 (gate_e1.py judge 가 만든다. 손으로 고치지 않는다)", "",
         "- 사전 등록: `results/v2/e1/PREREG.md`. 평가 시드 10000~10019 × 5000스텝, 결정적 상수 정책, "
         "G_γ 는 γ_train(0.9917), 괄호 t 는 평가 시드 짝지은 t(자유도 19, 기준 2.093)",
         f"- 기준: 공통 = C2-seg G_γ 가 C2 보다 높고 t > {T_CRIT}, 구간별 보행이 둘 이상. (a) 아사 비중 "
         f"{CRIT['starve_lo']}~{CRIT['starve_hi']}, energy<0.5 ≥ {CRIT['hungry_min']} (C2-seg). (b) C2-seg 걷기 > "
         f"{CRIT['walk_min']}. (c) 항상 걷기 아사율 < 항상 뛰기 아사율 (구성상 성립, sanity)", ""]
    for r in rounds.values():
        L += md_round(r)
        if "next" in r:
            L.append(f"- 다음: {r['next']['action']} — {r['next']['reason']}")
        L.append("")
    if final:
        L += ["## 종합", "", f"- **{final['verdict']}** ({final['round']}" +
              (f", {final['arm']}: R {final['run_mult']:g}, c_rest {final['c_rest']!r}, c_move {final['c_move']!r}, "
               f"e_walk {final['walk_eat']:g})" if final["verdict"] == "PASS" else f") — {final['reason']}"), ""]
    (out / "judge.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", default=None, help="출력 디렉터리. 기본 results/v2/e1 (시험 실행은 다른 곳에)")
    p = argparse.ArgumentParser(description="Gate E1 — v2.1 보행·대사 행동 게이트 (계획서 1-2)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("configs", parents=[common], help="회차의 팔 설정 yaml 을 만든다")
    s.add_argument("--round", required=True, choices=ROUNDS)
    s.add_argument("--run-mult", type=float, nargs="+", required=True, help="뛰기 대사 배수 R (걷기 배수 1 고정)")
    s.add_argument("--walk-eat", type=float, nargs="+", required=True, help="걷기 섭식 배수 e_walk")
    s = sub.add_parser("run", parents=[common], help="팔 하나를 돌린다 (끊기면 같은 명령으로 이어 간다)")
    s.add_argument("--round", required=True, choices=ROUNDS)
    s.add_argument("--arm", required=True)
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--smoke", action="store_true", help="도구 시험(작은 조건). --out 을 결과 디렉터리 밖으로 준다")
    sub.add_parser("judge", parents=[common], help="모든 회차를 판정해 judge.json·judge.md 를 만든다")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    args = build_parser().parse_args(argv)
    return {"configs": cmd_configs, "run": cmd_run, "judge": cmd_judge}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
