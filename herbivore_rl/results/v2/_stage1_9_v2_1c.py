"""1-9 확인층 — 대체안 v2.1 5시드 확인 (`results/v2/s1_9/PREREG.md`, 10-03 R5·갈림 5).

    # herbivore_rl/ 에서
    python results/v2/_stage1_9_v2_1c.py diag      # 시드 30~34 진단(1-3 명령 그대로) + 묶음 report·modecmp
    python results/v2/_stage1_9_v2_1c.py diag --hold   # 판정 모드 K24 진단 (PREREG 6절: T0 판정 모드 = hold)
    python results/v2/_stage1_v2_1.py --prefix v2_1c --seeds 30 31 32 33 34 --judge-mode hold   # 1-3 운영 정의로 집계
    python results/v2/_stage1_9_v2_1c.py rule      # 대체안 (a) 규칙 장면 기술 (평가 시드, L 세계)
    python results/v2/_stage1_9_v2_1c.py report    # s1_9/report.md

- diag: `_stage1_v2_1.py` 머리 주석의 진단 명령을 모델 `ckpt/v2/v2_1c_s<시드>.zip`·이름 `v2_1c_s<시드>` 로 돈다.
  C2·C2-seg 는 E1-b 선택 팔 상수(1-3 과 같은 값). 이미 결과 JSON 이 있으면 그 명령은 건너뛴다.
- rule: PREREG 4절 (a). 평가 시드 10000~10019 × 5000스텝에서 v2.1c 5모델을 L 세계(`configs/v2_2r_l.yaml`)에 두고
  '그대로'(관측 7만 넣음)와 '창 규칙'(창 안이면 speed 정지 → 반사 돌아보기, `probe_v2:window_stop`)을 판정 모드로 함께 잰다.
  판정이 아니라 기술이다(S2 '규칙 장면').
- report: 판정표를 맨 앞에 두는 150줄 이내 보고서. 판정 칸은 `stage1_v2_1c.json`(1-3 운영 정의)에서 그대로 옮긴다.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

RES = ROOT / "results" / "v2"
OUT = RES / "s1_9"
PREFIX = "v2_1c"
SEEDS = (30, 31, 32, 33, 34)
CONFIG = "configs/v2_1.yaml"
GAMMA = 0.9916661555611042
EVAL_SEEDS = list(range(10000, 10020))
T_CRIT = 2.093
C2 = ["0.9709889334578663", "0.7849404966375042", "0.2182330585135458", "0.03358694847233987", "0.4913744307309694"]
C2SEG = ["0.31542835092418386", "0.3637107709426226", "0.5701967704178796", "0.43860151346232035"]


def _run(cmd: list[str], done: Path | None, log) -> None:
    if done is not None and done.exists():
        print(f"  있음 — 건너뜀: {done.relative_to(ROOT)}", flush=True)
        return
    print("  $ " + " ".join(cmd), flush=True)
    r = subprocess.run([sys.executable] + cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise SystemExit(f"실패({r.returncode}): {' '.join(cmd)}")


def cmd_diag(a) -> int:
    w = str(a.workers)
    if a.hold:
        return diag_hold(w)
    with open(OUT / "diag.log", "a", encoding="utf-8") as log:
        for s in SEEDS:
            name = f"{PREFIX}_s{s}"
            model = f"ckpt/v2/{name}.zip"
            d = RES / f"diag_{name}"
            base = ["diagnose_v2.py", None, "--config", CONFIG, "--model", model, "--name", name]
            print(f"{name}", flush=True)
            _run(base[:1] + ["ablate"] + base[2:] + ["--workers", w], d / "ablate.json", log)
            _run(base[:1] + ["permute"] + base[2:] + ["--obs", "2", "4", "--workers", w], d / "permute.json", log)
            _run(base[:1] + ["constsearch"] + base[2:] + ["--workers", w, "--const-action", *C2],
                 d / "constsearch.json", log)
            _run(base[:1] + ["constsearch"] + base[2:] + ["--workers", w, "--seg-bins", "2:0.5", "4:0.5",
                                                          "--seg-dims", "speed", "--const-action", *C2SEG],
                 d / "constsearch_seg.json", log)
            _run(base[:1] + ["constsearch"] + base[2:] + ["--workers", w, "--out", f"results/v2/diag_{name}/g998",
                                                          "--tag", "c2seg_g998", "--g998", "--seg-bins", "2:0.5",
                                                          "4:0.5", "--seg-dims", "speed", "--base-action", *C2,
                                                          "--const-action", *C2SEG],
                 d / "g998" / "c2seg_g998.json", log)
            _run(["diagnose_v2.py", "ablate", "--config", CONFIG, "--model", model, "--name", f"{name}_stoch",
                  "--act-mode", "stochastic", "--workers", w], RES / f"diag_{name}_stoch" / "ablate.json", log)
            _run(base[:1] + ["curves"] + base[2:], d / "curves.json", log)
            _run(base[:1] + ["r2"] + base[2:], d / "r2.json", log)
        dirs = [f"{PREFIX}_s{s}" for s in SEEDS]
        _run(["diagnose_v2.py", "report", "--config", CONFIG, "--dirs", *dirs, "--name", PREFIX], None, log)
        _run(["diagnose_v2.py", "modecmp", "--config", CONFIG, "--out", f"results/v2/diag_{PREFIX}", "--tag", "modecmp",
              "--det", *dirs, "--stoch", *[f"{x}_stoch" for x in dirs]], RES / f"diag_{PREFIX}" / "modecmp.json", log)
    return 0


def diag_hold(w: str) -> int:
    """판정 모드 K24 진단: 판정에 쓰는 ablate·permute·constsearch(C2·C2-seg)를 `--act-mode hold --hold-k 24` 로 돈다.
    이름 `v2_1c_s<시드>_hold24` (디렉터리 `results/v2/diag_v2_1c_s<시드>_hold24/`)."""
    hk = ["--act-mode", "hold", "--hold-k", "24"]
    with open(OUT / "diag_hold.log", "a", encoding="utf-8") as log:
        for s in SEEDS:
            name = f"{PREFIX}_s{s}_hold24"
            model = f"ckpt/v2/{PREFIX}_s{s}.zip"
            d = RES / f"diag_{name}"
            base = ["--config", CONFIG, "--model", model, "--name", name, "--workers", w, *hk]
            print(name, flush=True)
            _run(["diagnose_v2.py", "ablate", *base], d / "ablate.json", log)
            _run(["diagnose_v2.py", "permute", *base, "--obs", "2", "4"], d / "permute.json", log)
            _run(["diagnose_v2.py", "constsearch", *base, "--const-action", *C2], d / "constsearch.json", log)
            _run(["diagnose_v2.py", "constsearch", *base, "--seg-bins", "2:0.5", "4:0.5", "--seg-dims", "speed",
                  "--const-action", *C2SEG], d / "constsearch_seg.json", log)
    return 0


def _paired(a, b) -> dict:
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    sd = float(d.std(ddof=1))
    t = float(d.mean() / (sd / math.sqrt(len(d)))) if sd > 0 else float("nan")
    return {"diff": float(d.mean()), "t": t, "sig": bool(math.isfinite(t) and abs(t) > T_CRIT)}


def cmd_rule(a) -> int:
    from env_v2.config import load_v2_config
    from env_v2.rollout import make_executor, public_row, run_specs
    from env_v2.world import OBS_THREAT_RECENCY

    mode = a.mode
    cfg = load_v2_config(ROOT / "configs" / "v2_2r_l.yaml")
    take = {"factory": "probe_v2:obs_take", "dims": list(range(7))}
    stop = {"factory": "probe_v2:window_stop", "speed_col": 4, "tr_col": OBS_THREAT_RECENCY,
            "theta": cfg.v2["features"]["vigil_window"]["theta"]}
    extra = {} if mode == "det" else {"mode": "hold", "hold_k": 24}
    specs = {}
    for s in SEEDS:
        pol = {"kind": "learned", "model": str((ROOT / "ckpt" / "v2" / f"{PREFIX}_s{s}.zip").resolve()), **extra}
        specs[f"s{s}|base"] = {"policy": pol, "wrap": [take]}
        specs[f"s{s}|rule"] = {"policy": pol, "wrap": [take, stop]}
    ex = make_executor(a.workers)
    try:
        res = run_specs(cfg, specs, EVAL_SEEDS, 5000, gamma=GAMMA, executor=ex)
    finally:
        if ex is not None:
            ex.shutdown()
    rows = {k: [public_row(r) for r in v] for k, v in res.items()}
    cols = ("g_gamma", "predation_rate", "starve_rate", "survival", "repro", "look_frac", "b1")
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": mode,
           "config": "configs/v2_2r_l.yaml", "eval_seeds": [EVAL_SEEDS[0], EVAL_SEEDS[-1]], "rows": rows, "cols": {}}
    for c in cols:
        base = np.mean([[r[c] for r in rows[f"s{s}|base"]] for s in SEEDS], axis=0)
        rule = np.mean([[r[c] for r in rows[f"s{s}|rule"]] for s in SEEDS], axis=0)
        out["cols"][c] = {"base": float(base.mean()), "rule": float(rule.mean()), **_paired(rule, base)}
    (OUT / "rule_scene.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for c, v in out["cols"].items():
        print(f"{c}: 그대로 {v['base']:.5f}, 규칙 {v['rule']:.5f}, 차 {v['diff']:+.5f} (t {v['t']:+.2f})")
    return 0


def cmd_report(a) -> int:
    d = json.loads((RES / f"stage1_{PREFIX}_hold24.json").read_text(encoding="utf-8"))
    rule = json.loads((OUT / "rule_scene.json").read_text(encoding="utf-8")) if (OUT / "rule_scene.json").exists() \
        else None
    judge = json.loads((RES / "v2_2r_explore" / "judge.json").read_text(encoding="utf-8"))
    L = ["# 1-9 확인층 — v2.1 5시드 확인 (대체안, 판정)", "",
         f"- 생성 {datetime.now(timezone.utc).isoformat(timespec='seconds')}. 사전 등록 `s1_9/PREREG.md`, 수치 원본 "
         f"`stage1_{PREFIX}_hold24.json`(1-3 운영 정의, 판정 모드 K24)·`s1_9/rule_scene.json`.",
         f"- 판정 모드: {judge['modes'].get('T0', {}).get('mode', '?')} (탐색 판정 T0, R1). 갈림: {judge['branch']}", ""]
    L += ["## 판정표", "", "| 주장 | 크기 | 쓸모 | 입력 의존 | 성립 |", "|---|---|---|---|---|"]
    # 쓸모는 10-03 결정 (1) '결과 지표 필수'(PREREG 3절 정정): 집계의 outcome_path 만 쓴다. B2 는 기술용이다
    for x in ("b1", "b2"):
        sz, us, dp = d["size"][x], d["usefulness"][x], d["dependence"][x]
        holds = bool(sz["holds"] and us["outcome_path"] and dp["holds"])
        L.append(f"| {x.upper()}{'' if x == 'b1' else ' (기술)'} | {sz['n_pass']}/{len(sz['pass_per_seed'])} "
                 f"(필요 {sz['need']}) | 결과 지표 {us['outcome_path']} (G_γ 경로 {us['g_path']}, 참고) | "
                 f"{dp['holds']} (통과 시드에서 {dp.get('holds_in_passed_seeds')}) | {holds} |")
    b1 = d["size"]["b1"]
    if not b1["holds"]:
        L.append(f"- B1 크기 {b1['n_pass']}/5 < 4 → PREREG 3절: B1 주장 '부분({b1['n_pass']}/5)'으로 기록하고 닫는다")
    lf = d["learning_failure"]["delta_c2seg_minus_c0"]
    L += ["", f"- 학습 실패 감지(E1-b C2-seg − C0, 묶음 IQM 95% CI): {lf['point']:+.3f} [{lf['lo']:+.3f}, {lf['hi']:+.3f}]"
          f" → {'학습 실패' if lf['lo'] > 0 else '유의하게 낮지 않다(학습 실패 아님)'}"]
    L += [f"- B1 시드별: {d['size']['b1']['per_seed']}"]
    L += [f"- B8: {d['b8']['pass_per_seed']}"]
    if rule:
        L += ["", "## 규칙 장면 (대체안 (a), 기술 — 판정 아님)", "", "| 열 | 그대로 | 창 규칙 | 차 (t) |", "|---|---|---|---|"]
        for c, v in rule["cols"].items():
            L.append(f"| {c} | {v['base']:.5f} | {v['rule']:.5f} | {v['diff']:+.5f} ({v['t']:+.2f}) |")
    (OUT / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("diag")
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--hold", action="store_true", help="판정 모드 K24 진단만 (PREREG 6절)")
    s = sub.add_parser("rule")
    s.add_argument("--workers", type=int, default=12)
    s.add_argument("--mode", choices=("det", "hold"), default="hold")
    sub.add_parser("report")
    a = p.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    return {"diag": cmd_diag, "rule": cmd_rule, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
