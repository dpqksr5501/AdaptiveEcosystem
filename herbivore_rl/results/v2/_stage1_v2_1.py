"""1-3 v2.1 평가(중간 묶음) 집계 — 진단 JSON → results/v2/stage1_v2_1.json.

계획서 `Docs/RL_Policy/RL_V2_PLAN.md` 1-3 행, 5.0 학습 실패 규칙, 6.1(원칙 4·7), 6.2 B1·B2·B8, 6.3 대조군·판정 규칙.
롤아웃은 돌리지 않는다. 아래 진단 명령이 남긴 JSON 을 읽어 묶는다. 개입 곡선(보행 비율)만 보정 표본 캐시
(`runs/v2_diag/v2_1_s<시드>/calib.npz`, 학습 시드 0~19 × 3000스텝, 평가 시드와 안 겹침)에 정책을 다시 씌워 계산한다.

    # herbivore_rl/ 에서. 학습 시드 s = 0, 1, 2
    python diagnose_v2.py ablate      --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s --workers 6
    python diagnose_v2.py permute     --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s --obs 2 4 --workers 6
    python diagnose_v2.py constsearch --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s --workers 6 \
        --const-action <E1-b C2 5개>
    python diagnose_v2.py constsearch --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s --workers 6 \
        --seg-bins 2:0.5 4:0.5 --seg-dims speed --const-action <E1-b C2-seg 4개>
    python diagnose_v2.py constsearch --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s --workers 6 \
        --out results/v2/diag_v2_1_s$s/g998 --tag c2seg_g998 --g998 --seg-bins 2:0.5 4:0.5 --seg-dims speed \
        --base-action <E1-b C2 5개> --const-action <E1-b C2-seg 4개>                # 참고: G_0.998
    python diagnose_v2.py ablate      --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s${s}_stoch \
        --act-mode stochastic --workers 6                                            # 확률 모드 (#29)
    python diagnose_v2.py curves --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s
    python diagnose_v2.py r2     --config configs/v2_1.yaml --model ckpt/v2/v2_1_s$s.zip --name v2_1_s$s
    # 묶음
    python diagnose_v2.py report  --config configs/v2_1.yaml --dirs v2_1_s0 v2_1_s1 v2_1_s2 --name v2_1
    python diagnose_v2.py modecmp --config configs/v2_1.yaml --out results/v2/diag_v2_1 --tag modecmp \
        --det v2_1_s0 v2_1_s1 v2_1_s2 --stoch v2_1_s0_stoch v2_1_s1_stoch v2_1_s2_stoch
    python results/v2/_stage1_v2_1.py

1-9 확인층(10-03, `results/v2/s1_9/PREREG.md`)은 같은 절차를 새 학습 시드에 쓴다. 모델·진단 이름의 앞부분과 시드만 바꾼다
(`--prefix v2_1c --seeds 30 31 32 33 34` → `ckpt/v2/v2_1c_s<시드>.zip`, `results/v2/diag_v2_1c_s<시드>/`,
`runs/v2_diag/v2_1c_s<시드>/calib.npz`, `results/v2/diag_v2_1c/modecmp.json`, 결과 `results/v2/stage1_v2_1c.json`).
인자 없이 부르면 1-3 그대로다(v2_1, 시드 0~2).
    python results/v2/_stage1_v2_1.py --prefix v2_1c --seeds 30 31 32 33 34
판정 모드(R1)가 K24 유지 표본이면 `--judge-mode hold` 를 준다. 그러면 판정 행(C0·대조군·C2·C2-seg·C4)을
`results/v2/diag_<prefix>_s<시드>_hold24/`(진단을 `--act-mode hold --hold-k 24` 로 돈 결과)에서 읽고, 결정·확률 모드
C0 는 '다른 모드' 한 줄 보고(`other_modes`: G_γ·B1·B2, 판정 모드와의 짝 t)로만 쓴다. 기존 '행동 모드'(확률 − 결정,
#29) 절은 결정 디렉터리 그대로 기술용으로 남는다. G_0.998·개입 곡선도 결정 모드 그대로(참고)다.
    python results/v2/_stage1_v2_1.py --prefix v2_1c --seeds 30 31 32 33 34 --judge-mode hold

운영 정의 (2026-10-02, 평가 롤아웃을 돌리기 전에 이 파일에 적었다. 기준값은 계획서 6.2·#13 의 사전 등록값 그대로):
- 조건: 결정 모드 결과는 모두 config_digest f068496361f9(`configs/v2_1.yaml` = E1-b B1 r2_5_ew0_5 팔), 평가 시드
  10000~10019 × 5000스텝, G 의 γ = 모델 학습 γ 0.9916661555611042, 끝 600스텝 제외, 앞 제외 0 이어야 한다.
  확률 모드는 같은 조건에 act_mode stochastic. 하나라도 다르면 멈춘다.
- C2·C2-seg 는 E1-b 선택 팔(B1 r2_5_ew0_5)의 상수 그대로다(새로 찾지 않는다). 진단 디렉터리에서 다시 잰 시드별 값이
  E1-b 결과와 같은지 확인한다(재현 검사). 상수라 학습 시드 축이 없어 같은 행을 학습 시드 수만큼 쓴다.
- 묶음 유의(6.1-4 의 두 층 가운데 학습 시드 층, 1단계 완료 기준의 "학습 시드 IQM 95% CI"): Δ = 대조군 − C0 의
  (학습 시드 × 평가 시드) 행렬 IQM, 층화 부트스트랩(층 = 평가 시드) 2000회·시드 0 의 95% CI 가 0 을 빼면 유의.
  평가 시드 층은 시드별 짝지은 t(자유도 19, |t| > 2.093)와, 평가 시드마다 학습 시드 평균을 낸 20쌍의 짝지은 t 로
  함께 적는다. 판정 문장은 묶음 CI 로 쓴다.
- 크기(6.3-1): 학습 시드마다 결정 모드 C0 의 B1(평가 시드 20개 평균) ≥ 0.3, B2 ≥ 0.1. 성립 = ceil(0.8·R) 시드 이상
  (1단계 완료 기준 '5시드 중 4시드'를 시드 수에 맞춘 것, 3시드면 3시드 모두). B1 거리 구간별 값은
  P(뛰기 | 구간) − P(뛰기 | 안 보임) 으로 보고만 한다.
- 쓸모(6.3-2, 결과 지표는 1단계 완료 기준의 짝): B1 = [피식률이 C1′·C2 둘 다보다 유의하게 낮다] 또는 [G_γ 가 C1′·C2
  둘 다보다 유의하게 높다]. B2 = [아사율이 C1′·C2 둘 다보다 유의하게 낮거나, 번식이 둘 다보다 유의하게 높다] 또는
  [G_γ 가 둘 다보다 유의하게 높다]. 묶음 CI 로 본다.
- 입력 의존(6.3-3): B1 은 C4-pred_dist-fix(관측 2 를 보정 평균으로 고정), B2 는 C4-energy-fix(관측 4). 크기를 넘은
  학습 시드마다 그 C4 의 같은 지표가 기준 아래면 그 시드에서 성립. 크기가 성립하고 크기를 넘은 시드 모두에서
  성립하면 성립. 순열(perm)과 엇갈린 짝(B1 ← energy, B2 ← pred_dist)은 보고만 한다.
- 행동 주장 성립 = 크기·쓸모·입력 의존 모두(6.3). 크기가 불성립이면 나머지는 값만 적는다.
  (결과를 본 뒤 더한 기술용 열, 판정 규칙은 그대로: `holds_in_passed_seeds` = 크기를 넘은 시드에서만 본 입력 의존,
  `c4_below_crit_all_seeds` = 모든 학습 시드에서 C4 고정 값이 기준 아래인가.)
- B8(2차, 잠정 기준): 학습 시드마다 b8(실제 보행 전환, 개체당 /초) ≤ 0.5. 명령 보행 전환 b8_cmd 도 적는다.
  넘으면 10절 #3(최소 유지 K)의 신호로 적는다.
- 학습 실패 규칙(5.0, 1-3 완료 기준): Δ G_γ(C2-seg − C0) 묶음 CI 하한 > 0 이면 "C0 이 C2-seg 보다 유의하게 낮다" →
  학습 실패(대응 순서 (a)~(d)). 아니면 "유의하게 낮지 않다". 시드별 t(C2-seg − C0 > 0, t > 2.093)도 적는다.
  C5(Utility v2)는 아직 없어 뺀다.
- 행동 모드(6.1-7, #29): Δ = 확률 − 결정(같은 모델·같은 평가 시드). G_γ·B1·B2 는 평가 시드마다 학습 시드 평균의
  짝지은 t |t| > 2.093 이고, Δ 행렬 평균의 층화 부트스트랩 95% CI 가 0 을 빼면 유의(0-7 PREREG 의 G 규칙과 같다).
  결과 지표 3개(수명·아사율·피식률)는 `diagnose_v2.py modecmp` 의 Holm 규칙(0-7 과 같다). 하나라도 유의하면 #29
  신호. 확률 모드의 B1·B2 가 기준을 넘는지도 적는다(판정은 결정 모드).
- 참고(판정 아님): G_0.998(γ 0.998, 10000스텝, 앞 500·끝 2500 제외)의 C0 − C2-seg·C0 − C2. 개입 곡선: 보정 표본에서
  관측 하나만 격자값으로 바꿨을 때 명령 보행 비율(결정 모드). pred_dist 는 포식자가 보이는 표본(관측 1 > 0)에서만 바꾼다.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import json  # noqa: E402
import math  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402

from diagnose_v2 import (  # noqa: E402
    T_CRIT, clean, col_means, excludes_zero, fmean, iqm, paired, save_json, stratified_bootstrap_ci,
)
from env_v2.rollout import build_policy  # noqa: E402

RES = ROOT / "results" / "v2"
PREFIX = "v2_1"
SEEDS = (0, 1, 2)
DET = {s: RES / f"diag_{PREFIX}_s{s}" for s in SEEDS}
STOCH = {s: RES / f"diag_{PREFIX}_s{s}_stoch" for s in SEEDS}
JUDGE_MODE, HOLD_K = "deterministic", None
JUDGE = DET                            # 판정 행을 읽는 디렉터리 (결정 모드면 DET 그대로)


def configure(prefix: str, seeds, judge_mode: str = "deterministic") -> None:
    """모델·진단 이름의 앞부분, 학습 시드, 판정 모드를 바꾼다(1-9 확인층). 기본값은 1-3 그대로다."""
    global PREFIX, SEEDS, DET, STOCH, JUDGE_MODE, HOLD_K, JUDGE
    PREFIX, SEEDS = str(prefix), tuple(int(x) for x in seeds)
    DET = {s: RES / f"diag_{PREFIX}_s{s}" for s in SEEDS}
    STOCH = {s: RES / f"diag_{PREFIX}_s{s}_stoch" for s in SEEDS}
    if judge_mode not in ("deterministic", "hold"):
        raise SystemExit(f"--judge-mode 는 deterministic 또는 hold 다: {judge_mode}")
    JUDGE_MODE, HOLD_K = judge_mode, (24 if judge_mode == "hold" else None)
    JUDGE = DET if judge_mode == "deterministic" else {s: RES / f"diag_{PREFIX}_s{s}_hold24" for s in SEEDS}

E1B = RES / "e1" / "B1" / "r2_5_ew0_5"
DIGEST = "f068496361f9"
GAMMA = 0.9916661555611042
EVAL_SEEDS = list(range(10000, 10020))
EVAL_STEPS = 5000
TAIL = 600
REPS, BOOT_SEED = 2000, 0

CRIT = {"b1": 0.3, "b2": 0.1, "b8": 0.5}
SIZE_FRAC = 0.8                       # 5시드 중 4시드 → ceil(0.8·R)

OUT_COLS = ["mean_return", "g_gamma", "survival", "repro", "predation_rate", "starve_rate", "starve_share"]
GAIT_COLS = ["stop_frac", "walk_frac", "run_frac", "stall_frac", "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd",
             "hungry_frac", "b1", "p_run_unseen", "p_run_d025", "p_run_d050", "p_run_d100",
             "b1_d025", "b1_d050", "b1_d100", "b2", "p_stop_hungry", "p_stop_full", "b8", "b8_cmd",
             "intake_per_step", "drain_per_step"]
BEH_COLS = ["cohesion_mean", "flee_dist_mean", "cover_frac", "react_pred", "react_hunger"]
COLS = OUT_COLS + GAIT_COLS + BEH_COLS
# 묶음 IQM·CI 를 내는 열 (시드별 평균은 COLS 전부를 남긴다)
KEY_COLS = OUT_COLS + ["stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd", "hungry_frac", "b1", "b1_d025",
                       "b1_d050", "b1_d100", "b2", "p_stop_hungry", "p_stop_full", "b8", "b8_cmd"]
# 쓸모에서 '낫다'의 방향: Δ = 대조군 − C0 가 이 부호면 C0 가 낫다
BETTER_IF_DELTA = {"g_gamma": -1, "predation_rate": +1, "starve_rate": +1, "repro": -1}


# --------------------------------------------------------------------- #
# 읽기와 조건 확인
# --------------------------------------------------------------------- #


def load(p: Path) -> dict:
    if not p.exists():
        raise SystemExit(f"{p} 가 없다")
    return json.loads(p.read_text(encoding="utf-8"))


def check_meta(d: dict, where: str, *, mode="deterministic", gamma=GAMMA, steps=EVAL_STEPS, tail=TAIL, head=0):
    m = d["meta"]
    want = {"config_digest": DIGEST, "eval_seeds": EVAL_SEEDS, "eval_steps": steps, "tail": tail}
    for k, v in want.items():
        if m.get(k) != v:
            raise SystemExit(f"{where}: {k}={m.get(k)!r} 인데 {v!r} 이어야 한다")
    if abs(float(m["gamma"]) - gamma) > 1e-12:
        raise SystemExit(f"{where}: γ {m['gamma']} ≠ {gamma}")
    if int(m.get("head") or 0) != head or (m.get("act_mode") or "deterministic") != mode:
        raise SystemExit(f"{where}: head/act_mode 가 다르다 ({m.get('head')}, {m.get('act_mode')})")
    if m.get("hold_k") != (HOLD_K if mode == "hold" else None):
        raise SystemExit(f"{where}: hold_k {m.get('hold_k')} 가 판정 조건과 다르다")


def with_derived(row: dict) -> dict:
    r = dict(row)
    u = r.get("p_run_unseen")
    for k in ("d025", "d050", "d100"):
        p = r.get(f"p_run_{k}")
        r[f"b1_{k}"] = (p - u) if (p is not None and u is not None) else None
    return r


def rows_of(d: dict, name: str) -> list[dict]:
    rows = [with_derived(r) for r in d["per_seed"][name]]
    if [r["seed"] for r in rows] != EVAL_SEEDS:
        raise SystemExit(f"{name}: 평가 시드 순서가 다르다")
    return rows


def vec(rows: list[dict], col: str) -> np.ndarray:
    return np.array([float("nan") if r.get(col) is None else float(r[col]) for r in rows], dtype=np.float64)


def model_sha(d: dict) -> str | None:
    return d["meta"].get("model_sha1")


def collect() -> tuple[dict, dict, dict]:
    """학습 시드별 {대조군: 행 목록} (결정 모드), 확률 모드 C0 등, 재현 검사 결과."""
    det, stoch, repro = {}, {}, {}
    e1_c2 = load(E1B / "constsearch.json")
    e1_seg = load(E1B / "constsearch_seg.json")
    check_meta(e1_c2, "E1-b C2")
    check_meta(e1_seg, "E1-b C2-seg")
    for s in SEEDS:
        abl = load(JUDGE[s] / "ablate.json")
        per = load(JUDGE[s] / "permute.json")
        c2 = load(JUDGE[s] / "constsearch.json")
        seg = load(JUDGE[s] / "constsearch_seg.json")
        for d, w in ((abl, "ablate"), (per, "permute"), (c2, "constsearch"), (seg, "constsearch_seg")):
            check_meta(d, f"s{s} {w}", mode=JUDGE_MODE)
        sha = {model_sha(x) for x in (abl, per, c2, seg)}
        if len(sha) != 1 or None in sha:
            raise SystemExit(f"s{s}: 모델 sha1 이 결과마다 다르다 {sha}")
        if [float(x) for x in c2["best"]] != [float(x) for x in e1_c2["best"]]:
            raise SystemExit(f"s{s}: C2 상수가 E1-b 와 다르다")
        if ([float(x) for x in seg["best"]] != [float(x) for x in e1_seg["best"]]
                or seg["bins"] != e1_seg["bins"] or seg["dims"] != e1_seg["dims"]
                or [float(x) for x in seg["base_action"]] != [float(x) for x in e1_seg["base_action"]]):
            raise SystemExit(f"s{s}: C2-seg 표가 E1-b 와 다르다")
        rows = {name: rows_of(abl, name) for name in abl["per_seed"]}
        c0_perm = rows_of(per, "C0")
        if c0_perm != rows["C0"]:
            raise SystemExit(f"s{s}: permute 의 C0 가 ablate 의 C0 와 다르다")
        for name in per["per_seed"]:
            if name != "C0":
                rows[name] = rows_of(per, name)
        rows["C2"] = rows_of(c2, "C2")
        rows["C2-seg"] = rows_of(seg, "C2-seg")
        if rows_of(c2, "C0") != rows["C0"] or rows_of(seg, "C0") != rows["C0"]:
            raise SystemExit(f"s{s}: constsearch 의 C0 가 ablate 의 C0 와 다르다")
        det[s] = rows
        repro[s] = {"C2": rows_of(c2, "C2") == rows_of(e1_c2, "C2"),
                    "C2-seg": rows_of(seg, "C2-seg") == rows_of(e1_seg, "C2-seg")}
        st = load(STOCH[s] / "ablate.json")
        check_meta(st, f"s{s} stoch", mode="stochastic")
        if model_sha(st) != model_sha(abl):
            raise SystemExit(f"s{s}: 확률 모드 결과의 모델이 다르다")
        stoch[s] = {name: rows_of(st, name) for name in st["per_seed"]}
        if JUDGE_MODE != "deterministic":      # 결정 모드 C0 (다른 모드 한 줄 보고, '행동 모드' 절의 기준)
            dabl = load(DET[s] / "ablate.json")
            check_meta(dabl, f"s{s} det")
            if model_sha(dabl) != model_sha(abl):
                raise SystemExit(f"s{s}: 결정 모드 결과의 모델이 다르다")
            stoch[s]["_det_C0"] = rows_of(dabl, "C0")
    return det, stoch, repro


# --------------------------------------------------------------------- #
# 통계
# --------------------------------------------------------------------- #


def matrix(by_seed: dict, name: str, col: str) -> np.ndarray:
    return np.array([vec(by_seed[s][name], col) for s in SEEDS])


def paired_nan(a: np.ndarray, b: np.ndarray) -> dict:
    """NaN 쌍을 뺀 짝지은 t (B1 처럼 분모가 0 인 시드가 있을 수 있다)."""
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 2:
        return {"diff": float("nan"), "t": float("nan"), "sig": False, "n": int(ok.sum())}
    r = paired(a[ok], b[ok])
    r["n"] = int(ok.sum())
    return r


def bundle_delta(by_seed: dict, name: str, col: str, ref: str = "C0") -> dict:
    A, B = matrix(by_seed, name, col), matrix(by_seed, ref, col)
    D = A - B
    ci = stratified_bootstrap_ci(D, stat=iqm, reps=REPS, seed=BOOT_SEED)
    lvl = stratified_bootstrap_ci(A, stat=iqm, reps=REPS, seed=BOOT_SEED)
    t_mean = paired_nan(col_means(A), col_means(B))
    return {"iqm": lvl, "delta_iqm": ci, "delta_mean": fmean(D), "ci_excludes_0": excludes_zero(ci),
            "t_seedmean": t_mean,
            "per_seed": {s: {"mean": fmean(A[i]), "ref_mean": fmean(B[i]), **paired_nan(A[i], B[i])}
                         for i, s in enumerate(SEEDS)}}


def per_seed_means(by_seed: dict, name: str) -> dict:
    return {s: {c: fmean(vec(by_seed[s][name], c)) for c in COLS} for s in SEEDS}


def better(delta: dict, col: str) -> bool:
    """묶음 CI 로 C0 가 대조군보다 '낫다'."""
    ci = delta["delta_iqm"]
    if not delta["ci_excludes_0"]:
        return False
    return (ci["lo"] > 0) if BETTER_IF_DELTA[col] > 0 else (ci["hi"] < 0)


# --------------------------------------------------------------------- #
# 개입 곡선 (보정 표본 캐시 위, 결정 모드)
# --------------------------------------------------------------------- #

PD_GRID = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.7, 0.85, 1.0]
EN_GRID = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]


def gait_split(a: np.ndarray) -> dict:
    s = np.asarray(a)[:, 4]
    return {"stop": float(np.mean(s < 1 / 3)), "walk": float(np.mean((s >= 1 / 3) & (s < 2 / 3))),
            "run": float(np.mean(s >= 2 / 3)), "speed_mean": float(np.mean(s))}


def intervention(seed: int) -> dict:
    cal = ROOT / "runs" / "v2_diag" / f"{PREFIX}_s{seed}" / "calib.npz"
    with np.load(cal, allow_pickle=False) as z:
        obs = np.asarray(z["obs"], dtype=np.float32)
    pol = build_policy({"kind": "learned", "model": str((ROOT / "ckpt" / "v2" / f"{PREFIX}_s{seed}.zip").resolve())})

    def act(o):
        return np.concatenate([np.asarray(pol(o[i:i + 8192]), np.float64) for i in range(0, len(o), 8192)])

    seen = obs[:, 1] > 0
    out = {"samples": int(len(obs)), "seen_samples": int(seen.sum()),
           "actual_all": gait_split(act(obs)), "actual_seen": gait_split(act(obs[seen])),
           "actual_unseen": gait_split(act(obs[~seen])), "pred_dist_seen": [], "energy_all": []}
    for v in PD_GRID:
        o = obs[seen].copy()
        o[:, 2] = v
        out["pred_dist_seen"].append({"x": v, **gait_split(act(o))})
    for v in EN_GRID:
        o = obs.copy()
        o[:, 4] = v
        out["energy_all"].append({"x": v, **gait_split(act(o))})
    return out


# --------------------------------------------------------------------- #
# 본체
# --------------------------------------------------------------------- #


def main() -> int:
    det, stoch, repro = collect()
    names = list(det[SEEDS[0]].keys())
    R = len(SEEDS)
    need = math.ceil(SIZE_FRAC * R)

    controls = {}
    for name in names:
        entry = {"per_seed_mean": per_seed_means(det, name)}
        if name != "C0":
            entry["vs_C0"] = {c: bundle_delta(det, name, c) for c in KEY_COLS}
        else:
            entry["level"] = {c: stratified_bootstrap_ci(matrix(det, "C0", c), stat=iqm, reps=REPS, seed=BOOT_SEED)
                              for c in KEY_COLS}
        controls[name] = entry

    c0 = controls["C0"]["per_seed_mean"]

    # 크기
    size = {}
    for x in ("b1", "b2"):
        vals = {s: c0[s][x] for s in SEEDS}
        ok = {s: bool(np.isfinite(v) and v >= CRIT[x]) for s, v in vals.items()}
        size[x] = {"crit": CRIT[x], "per_seed": vals, "pass_per_seed": ok, "n_pass": sum(ok.values()),
                   "need": need, "holds": sum(ok.values()) >= need,
                   "bundle_iqm": controls["C0"]["level"][x]}

    # 쓸모
    def useful(outcomes: list[str]) -> dict:
        d = {}
        for ref in ("C1'", "C2"):
            d[ref] = {c: better(controls[ref]["vs_C0"][c], c) for c in ["g_gamma"] + outcomes}
        out_ok = any(all(d[ref][c] for ref in ("C1'", "C2")) for c in outcomes)
        g_ok = all(d[ref]["g_gamma"] for ref in ("C1'", "C2"))
        return {"by_ref": d, "outcome_path": out_ok, "g_path": g_ok, "holds": bool(out_ok or g_ok)}

    usefulness = {"b1": useful(["predation_rate"]), "b2": useful(["starve_rate", "repro"])}

    # 입력 의존
    dep_ctrl = {"b1": "C4-pred_dist-fix", "b2": "C4-energy-fix"}
    cross = {"b1": ["C4-pred_dist-perm", "C4-energy-fix", "C4-energy-perm"],
             "b2": ["C4-energy-perm", "C4-pred_dist-fix", "C4-pred_dist-perm"]}
    dependence = {}
    for x, ctrl in dep_ctrl.items():
        cm = controls[ctrl]["per_seed_mean"]
        per = {}
        for s in SEEDS:
            v = cm[s][x]
            per[s] = {"c0": c0[s][x], "c4": v, "c0_pass": size[x]["pass_per_seed"][s],
                      "drops": bool(size[x]["pass_per_seed"][s] and np.isfinite(v) and v < CRIT[x])}
        passed = [s for s in SEEDS if size[x]["pass_per_seed"][s]]
        holds = bool(size[x]["holds"] and all(per[s]["drops"] for s in passed))
        # 기술용(판정 규칙은 위 holds 그대로): 크기를 넘은 시드에서만 본 입력 의존, 모든 시드에서 C4 값이 기준 아래인가
        in_passed = bool(passed and all(per[s]["drops"] for s in passed))
        below_all = bool(all(np.isfinite(per[s]["c4"]) and per[s]["c4"] < CRIT[x] for s in SEEDS))
        dependence[x] = {"control": ctrl, "per_seed": per, "holds": holds,
                         "holds_in_passed_seeds": in_passed, "c4_below_crit_all_seeds": below_all,
                         "report_only": {c: {s: controls[c]["per_seed_mean"][s][x] for s in SEEDS}
                                         for c in cross[x]}}

    claims = {x: {"size": size[x]["holds"], "useful": usefulness[x]["holds"], "dependence": dependence[x]["holds"],
                  "holds": bool(size[x]["holds"] and usefulness[x]["holds"] and dependence[x]["holds"])}
              for x in ("b1", "b2")}

    # B8
    b8 = {"crit": CRIT["b8"], "per_seed": {s: c0[s]["b8"] for s in SEEDS},
          "per_seed_cmd": {s: c0[s]["b8_cmd"] for s in SEEDS},
          "pass_per_seed": {s: bool(c0[s]["b8"] <= CRIT["b8"]) for s in SEEDS}}

    # 학습 실패 규칙
    lf = controls["C2-seg"]["vs_C0"]["g_gamma"]
    lf_c2 = controls["C2"]["vs_C0"]["g_gamma"]
    learn_fail = {
        "delta_c2seg_minus_c0": lf["delta_iqm"], "delta_mean": lf["delta_mean"], "t_seedmean": lf["t_seedmean"],
        "per_seed": lf["per_seed"],
        "c0_sig_lower": bool(lf["ci_excludes_0"] and lf["delta_iqm"]["lo"] > 0),
        "c0_sig_higher": bool(lf["ci_excludes_0"] and lf["delta_iqm"]["hi"] < 0),
        "seed_sig_lower": {s: bool(v["t"] is not None and np.isfinite(v["t"]) and v["diff"] > 0 and v["t"] > T_CRIT)
                           for s, v in lf["per_seed"].items()},
        "vs_C2": {"delta_c2_minus_c0": lf_c2["delta_iqm"], "t_seedmean": lf_c2["t_seedmean"],
                  "per_seed": lf_c2["per_seed"]},
    }
    learn_fail["verdict"] = "학습 실패" if learn_fail["c0_sig_lower"] else "유의하게 낮지 않다"

    # 행동 모드
    mode = {}
    for c in ["g_gamma", "b1", "b2", "b8", "b8_cmd", "survival", "starve_rate", "predation_rate", "repro",
              "run_frac_cmd", "stop_frac_cmd", "walk_frac_cmd", "b1_d025", "b1_d050", "b1_d100"]:
        Dm = matrix(det, "C0", c) if JUDGE_MODE == "deterministic" else matrix(stoch, "_det_C0", c)
        Sm = matrix(stoch, "C0", c)
        t = paired_nan(col_means(Sm), col_means(Dm))
        ci = stratified_bootstrap_ci(Sm - Dm, stat=fmean, reps=REPS, seed=BOOT_SEED)
        row = {"det": fmean(Dm), "stoch": fmean(Sm), **t, "ci": ci, "ci_excludes_0": excludes_zero(ci),
               "per_seed_stoch": {s: fmean(Sm[i]) for i, s in enumerate(SEEDS)}}
        if c in ("g_gamma", "b1", "b2"):
            row["sig"] = bool(t["sig"] and row["ci_excludes_0"])
        mode[c] = row
    mc = load(RES / f"diag_{PREFIX}" / "modecmp.json")
    holm_rows = {c: mc["groups"][0]["cols"][c] for c in ("survival", "starve_rate", "predation_rate")}
    mode_trigger = bool(any(mode[c]["sig"] for c in ("g_gamma", "b1", "b2"))
                        or any(bool(r.get("verdict")) for r in holm_rows.values()))
    stoch_size = {x: {s: mode[x]["per_seed_stoch"][s] for s in SEEDS} for x in ("b1", "b2")}

    # 다른 모드 한 줄 보고 (R1: 판정 모드가 아닌 모드는 G_γ·B1·B2 만, 판정 모드와의 짝 t = 다른 모드 − 판정 모드)
    other_modes = {}
    if JUDGE_MODE != "deterministic":
        for label, key in (("deterministic", "_det_C0"), ("stochastic", "C0")):
            other_modes[label] = {c: {"judged": fmean(matrix(det, "C0", c)), "other": fmean(matrix(stoch, key, c)),
                                      **paired_nan(col_means(matrix(stoch, key, c)), col_means(matrix(det, "C0", c)))}
                                  for c in ("g_gamma", "b1", "b2")}

    # 참고: G_0.998
    g998 = {}
    for s in SEEDS:
        d = load(DET[s] / "g998" / "c2seg_g998.json")
        check_meta(d, f"s{s} g998", gamma=0.998, steps=10000, tail=2500, head=500)
        g998[s] = {k: rows_of(d, k) for k in d["per_seed"]}
    g998_out = {}
    for name in ("C2-seg", "C2"):
        g998_out[name] = bundle_delta(g998, name, "g_gamma")
    g998_out["C0_level"] = stratified_bootstrap_ci(matrix(g998, "C0", "g_gamma"), stat=iqm, reps=REPS,
                                                   seed=BOOT_SEED)

    # 개입 곡선
    curves = {s: intervention(s) for s in SEEDS}

    data = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "python results/v2/_stage1_v2_1.py" + ("" if PREFIX == "v2_1" else
                                                           f" --prefix {PREFIX} --seeds {' '.join(map(str, SEEDS))}"),
        "condition": {"config": "configs/v2_1.yaml", "config_digest": DIGEST, "gamma": GAMMA,
                      "eval_seeds": [EVAL_SEEDS[0], EVAL_SEEDS[-1]], "eval_steps": EVAL_STEPS, "tail": TAIL,
                      "train_seeds": list(SEEDS), "models": {s: f"ckpt/v2/{PREFIX}_s{s}.zip" for s in SEEDS},
                      "judge_mode": JUDGE_MODE, "hold_k": HOLD_K,
                      "model_sha1": {s: load(DET[s] / "ablate.json")["meta"]["model_sha1"] for s in SEEDS},
                      "c2_source": str(E1B.relative_to(ROOT)).replace("\\", "/"),
                      "reps": REPS, "boot_seed": BOOT_SEED, "t_crit": T_CRIT, "size_need": need},
        "reproduction_e1b": repro,
        "controls": controls,
        "size": size, "usefulness": usefulness, "dependence": dependence, "claims": claims,
        "b8": b8, "learning_failure": learn_fail,
        "mode": {"cols": mode, "holm_outcomes": holm_rows, "trigger": mode_trigger, "stoch_size": stoch_size},
        "other_modes": other_modes,
        "g998": g998_out,
        "intervention": curves,
    }
    out = RES / (f"stage1_{PREFIX}.json" if JUDGE_MODE == "deterministic" else f"stage1_{PREFIX}_hold24.json")
    save_json(out, clean(data))
    print(f"저장: {out}")
    summary(data)
    return 0


def f(v, spec=".3f") -> str:
    return "—" if v is None or not np.isfinite(float(v)) else format(float(v), spec)


def summary(d: dict) -> None:
    ctrls = d["controls"]
    print("재현 검사(E1-b 와 같은가):", d["reproduction_e1b"])
    cols = ["g_gamma", "mean_return", "survival", "repro", "predation_rate", "starve_rate", "starve_share",
            "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd", "b1", "b2", "b8"]
    for s in SEEDS:
        print(f"\n== 학습 시드 {s} (괄호: 대조군 − C0 짝지은 t)")
        for name, e in ctrls.items():
            m = e["per_seed_mean"][s]
            parts = []
            for c in cols:
                v = f(m[c], ".5f" if c in ("predation_rate", "starve_rate") else ".3f")
                if name != "C0":
                    t = e["vs_C0"][c]["per_seed"][s]["t"]
                    if t is not None and np.isfinite(t):
                        v += f"({t:+.2f})"
                parts.append(f"{c}={v}")
            print(f"  {name:20s} " + " ".join(parts))
    print("\n== 묶음 Δ(대조군 − C0) IQM [CI]")
    for name, e in ctrls.items():
        if name == "C0":
            continue
        parts = []
        for c in ("g_gamma", "survival", "repro", "predation_rate", "starve_rate", "b1", "b2"):
            x = e["vs_C0"][c]["delta_iqm"]
            spec = ".5f" if c in ("predation_rate", "starve_rate") else ".3f"
            parts.append(f"{c} {f(x['point'], spec)} [{f(x['lo'], spec)}, {f(x['hi'], spec)}]"
                         f"{'*' if e['vs_C0'][c]['ci_excludes_0'] else ''}")
        print(f"  {name:20s} " + " | ".join(parts))
    print("\n크기", json.dumps({k: {"per_seed": v["per_seed"], "holds": v["holds"]} for k, v in d["size"].items()},
                              ensure_ascii=False))
    print("쓸모", json.dumps({k: v["holds"] for k, v in d["usefulness"].items()}))
    print("입력 의존", json.dumps({k: {"holds": v["holds"], "per_seed": v["per_seed"]} for k, v in d["dependence"].items()},
                                ensure_ascii=False))
    print("판정", d["claims"])
    print("B8", d["b8"])
    lf = d["learning_failure"]
    print("학습 실패:", lf["verdict"], lf["delta_c2seg_minus_c0"], lf["t_seedmean"], lf["seed_sig_lower"])
    print("모드:", {c: (f(r["det"]), f(r["stoch"]), f(r["t"], "+.2f"), r.get("sig")) for c, r in d["mode"]["cols"].items()},
          "trigger", d["mode"]["trigger"])
    print("G998:", {k: (v["delta_iqm"] if "delta_iqm" in v else v) for k, v in d["g998"].items()})


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="v2_1")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--judge-mode", choices=("deterministic", "hold"), default="deterministic")
    a = ap.parse_args()
    configure(a.prefix, a.seeds, a.judge_mode)
    sys.exit(main())
