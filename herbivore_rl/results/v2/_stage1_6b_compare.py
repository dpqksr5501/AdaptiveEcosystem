"""1-6b 학습 실패 대응 비교(팔 A·B × 학습 시드 3) — 학습 전·후 확인, 비교 지표, 선택 → results/v2/s1_6b/compare.json.

사전 등록은 `results/v2/s1_6b/PREREG.md` 다(2026-10-03, 학습 전). 이 파일은 그 문서의 1~4절(팔 정의, 비교 평가, 비교
지표, 선택 규칙)을 옮긴 것이고, 둘이 어긋나면 PREREG 가 기준이다. 선택한 팔의 1-6 판정 재실행(PREREG 5절)은
`results/v2/_stage1_6_v2_2.py --prefix v2_2<팔> --sdir s1_6b --seeds 5 6 7 8 9` 가 한다(판정 규칙은 1-6 그대로).

하위 명령 (작업 디렉터리 herbivore_rl/):
    python results/v2/_stage1_6b_compare.py precheck --arms a b --seeds 0 1 2    # 학습 전: 설정 지문·새 이름 확인
    python results/v2/_stage1_6b_compare.py checktrain --arms a b --seeds 0 1 2  # 학습 뒤: 학습 메타 = 팔 정의
    python results/v2/_stage1_6b_compare.py compare      # 진단 뒤: 비교 지표와 선택 → s1_6b/compare.json
    python results/v2/_stage1_6b_compare.py selected     # compare.json 의 선택 팔(a|b), 후보가 없으면 빈 줄
    python results/v2/_stage1_6b_compare.py armargs --arm a   # 그 팔의 train_v2.py 학습 옵션
판정 재실행 앞에는 `precheck --arms <선택 팔> --seeds 5 6 7 8 9` 가 compare.json 의 선택과 같은 팔인지도 본다.
`--res`·`--ckpt`·`--cache`·`--tb`·`--out`·`--smoke`·`--collapse-step` 은 도구 시험(scratchpad)용이다. `--smoke` 는 평가
시드·스텝을 결과 meta 에서 읽고, E2 재현 검사와 학습량(20M)·중간 저장 검사를 건너뛴다(판정·선택에 쓰지 않는다).

운영 정의 요약 (자세한 것은 PREREG 1~4절):
- 팔 A = `--ent-coef 3e-3`(경계 시작 편향은 설정의 −0.84 그대로), 팔 B = `--init-bias vigilance=0`(ent_coef 는
  configs/ppo_best.yaml 튜닝값 그대로). 세계 설정은 둘 다 configs/v2_2.yaml(config_digest efc8f775f1e1) 그대로다.
- 비교 평가(결정 모드): 평가 시드 10000~10019 × 5000스텝, γ 0.9916661555611042, 끝 600 제외. 학습 시드 값 = 평가 시드
  20개 평균. 확률 모드는 같은 조건의 기록이다(선택에 쓰지 않는다).
- 탐색 붕괴 신호(학습 시드마다): TensorBoard `vig/frac` 의 5,000,000 이상 첫 롤아웃 값 < 0.01, 또는 결정 모드 C0 의
  경계 비율(`vig_frac`, 평가 시드 평균)이 0 보다 크지 않다. 팔에 붕괴가 없다 = 학습 시드 3개 모두 신호가 없다.
- 학습 실패(팔마다): Δ G_γ = E2 A-허용 C2-seg − C0 의 (학습 시드 3 × 평가 시드 20) 행렬 IQM, 층화 부트스트랩
  2000회·시드 0 의 95% CI 하한 > 0.
- 선택: (1) 학습 실패가 아닌 팔 (2) 그중 붕괴가 없는 팔 (3) 둘이면 결정 모드 C0 G_γ IQM 차(A − B, 팔마다 학습 시드를
  따로 복원추출하는 층화 부트스트랩 2000회·시드 0, 95% CI)가 0 을 빼면 높은 팔, 아니면 B1·B3 크기 통과 시드 수 합이
  많은 팔, 같으면 팔 A. 후보가 없으면 선택하지 않는다(판정 재실행 없이 멈춤).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import warnings  # noqa: E402

import numpy as np  # noqa: E402

import _stage1_6_v2_2 as J  # noqa: E402  (1-6 집계: 조건 검사·행 읽기·묶음 통계를 그대로 쓴다)
from diagnose_v2 import config_digest, excludes_zero, fmean, iqm, model_fingerprint, save_json  # noqa: E402
from diagnose_v2 import clean, stratified_bootstrap_ci  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402

REF = J.REF
PPO_BEST = ROOT / "configs" / "ppo_best.yaml"
TUNED_ENT_COEF = 0.0008971496690499397        # configs/ppo_best.yaml params.ent_coef (precheck·checktrain 이 확인)

# PREREG 1절: 두 팔. 다른 것은 모두 같다(설정 configs/v2_2.yaml, γ, 20M, 무작위 초기화, speed 편향 0).
ARMS = {
    "a": {"prefix": "v2_2a", "what": "ent_coef 3e-3 (경계 시작 편향 −0.84, 설정 그대로)",
          "ent_coef": 3e-3, "ent_coef_source": "cli",
          "init_action_bias": {"vigilance": -0.84}, "init_action_bias_source": {"vigilance": "config"},
          "train_args": ["--ent-coef", "3e-3"]},
    "b": {"prefix": "v2_2b", "what": "경계 시작 편향 0 (ent_coef 튜닝값 그대로)",
          "ent_coef": TUNED_ENT_COEF, "ent_coef_source": "ppo_config",
          "init_action_bias": {"vigilance": 0.0}, "init_action_bias_source": {"vigilance": "cli"},
          "train_args": ["--init-bias", "vigilance=0"]},
}
COMPARE_SEEDS = (0, 1, 2)                      # 비교 학습 시드 (PREREG 1절)
JUDGE_SEEDS = (5, 6, 7, 8, 9)                  # 판정 재실행 학습 시드 (PREREG 5절, 비교·1-6 과 겹치지 않는다)
TRAIN_STEPS = 20_000_000
SAVE_AT = 10_000_000
COLLAPSE_STEP = 5_000_000                      # 계획서 4.7 '5M 시점' = 이 값 이상 첫 롤아웃
COLLAPSE_FRAC = 0.01                           # 4.7 '경계 비율 1% 미만'
TIE_ARM = "a"
SEG = "C2-seg-E2"                              # E2 A-허용 C2-seg (results/v2/e2/V0/d0_95)
SIZE_CLAIMS = ("B1", "B2", "B3")               # 크기 기준은 1-6 그대로 (J.PRIMARY: b1 ≥ 0.3, b2 ≥ 0.1, b3_truth ≥ 0.2)
SELECT_CLAIMS = ("B1", "B3")                   # 선택 규칙 (3) 의 크기 통과 시드 수 합
REC_COLS = ["g_gamma", "b1", "b2", "b3_truth", "b3_narrow", "starve_rate", "predation_rate", "survival", "repro",
            "vig_frac", "p_vig_recent_truth", "p_vig_calm_truth", "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd",
            "p_stop_hungry", "p_stop_full", "b8", "b8_cmd", "b8_vig"]
TB_TAGS = ["vig/frac", "act/vigilance_mean", "act/vigilance_std", "act/speed_std", "policy/vigilance_log_std",
           "policy/speed_log_std"]


# --------------------------------------------------------------------- #
# 공용
# --------------------------------------------------------------------- #


def run_name(arm: str, seed: int) -> str:
    return f"{ARMS[arm]['prefix']}_s{int(seed)}"


def tuned_ent_coef() -> float:
    import yaml

    return float(yaml.safe_load(PPO_BEST.read_text(encoding="utf-8"))["params"]["ent_coef"])


def boot_diff_stat(A, B, stat=iqm, reps: int = J.REPS, seed: int = J.BOOT_SEED, alpha: float = 0.05) -> dict:
    """서로 다른 두 팔의 stat(A) − stat(B) 층화 부트스트랩 퍼센타일 CI.

    A 는 (Ra 학습 시드, T 평가 시드), B 는 (Rb, T). 층(평가 시드)마다 팔마다 학습 시드를 **따로** 복원추출한다 —
    두 팔이 같은 시드 번호를 써도 다른 학습이라 짝짓지 않는다. 난수 순서는 `diagnose_v2.stratified_bootstrap_diff`
    와 같다(stat 이 평균이면 그 함수와 같은 값).
    """
    A, B = np.asarray(A, dtype=np.float64), np.asarray(B, dtype=np.float64)
    if A.ndim != 2 or B.ndim != 2 or A.shape[1] != B.shape[1]:
        raise ValueError(f"(학습 시드, 평가 시드) 행렬 둘의 층 수가 같아야 한다: {A.shape} vs {B.shape}")
    T = A.shape[1]
    rng = np.random.default_rng(seed)
    cols = np.arange(T)[None, None, :]
    ia = rng.integers(0, A.shape[0], size=(reps, A.shape[0], T))
    ib = rng.integers(0, B.shape[0], size=(reps, B.shape[0], T))
    a_s, b_s = A[ia, cols], B[ib, cols]
    vals = np.array([stat(a_s[k]) - stat(b_s[k]) for k in range(reps)])
    lo, hi = np.nanpercentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": float(stat(A) - stat(B)), "lo": float(lo), "hi": float(hi),
            "runs": [int(A.shape[0]), int(B.shape[0])], "strata": int(T), "reps": int(reps), "boot_seed": int(seed)}


def select_arm(summ: dict, g_diff: dict) -> dict:
    """PREREG 4절 선택 규칙. `summ[arm]` = {"learning_failure", "collapse", "n_pass": {B1, B3 …}},
    `g_diff` = 결정 모드 C0 G_γ IQM 차 A − B 의 CI (`boot_diff_stat`). 결과를 보기 전에 고정한 순서 그대로다."""
    arms = list(ARMS)
    trace = []
    step1 = [x for x in arms if not summ[x]["learning_failure"]]
    trace.append(f"(1) 학습 실패가 아닌 팔: {step1 or '없음'}")
    step2 = [x for x in step1 if not summ[x]["collapse"]]
    trace.append(f"(2) 그중 붕괴가 없는 팔: {step2 or '없음'}")
    counts = {x: int(sum(summ[x]["n_pass"][c] for c in SELECT_CLAIMS)) for x in arms}
    used = None
    if not step2:
        arm = None
        trace.append("(3) 후보가 없다 → 판정 재실행을 하지 않고 멈춘다(다음은 사람: 5.0 (b)~(d) 또는 범위 축소)")
    elif len(step2) == 1:
        arm = step2[0]
        trace.append(f"(3) 남은 팔이 하나 → {arm}")
    else:
        if excludes_zero(g_diff):
            arm = "a" if g_diff["lo"] > 0 else "b"
            used = "g_gamma_iqm"
            trace.append(f"(3) G_γ IQM 차 A − B {g_diff['point']:+.3f} [{g_diff['lo']:+.3f}, {g_diff['hi']:+.3f}] 가 0 을 "
                         f"뺀다 → {arm}")
        elif counts["a"] != counts["b"]:
            arm = max(arms, key=lambda x: counts[x])
            used = "b1_b3_pass_count"
            trace.append(f"(3) G_γ IQM 차 A − B {g_diff['point']:+.3f} [{g_diff['lo']:+.3f}, {g_diff['hi']:+.3f}] 가 0 을 "
                         f"포함 → B1·B3 크기 통과 시드 수 합 {counts} → {arm}")
        else:
            arm = TIE_ARM
            used = "tie"
            trace.append(f"(3) G_γ IQM 차가 0 을 포함하고 B1·B3 통과 시드 수 합도 같다 {counts} → 팔 {TIE_ARM}")
    return {"arm": arm, "prefix": ARMS[arm]["prefix"] if arm else None,
            "train_args": ARMS[arm]["train_args"] if arm else None,
            "judge_seeds": list(JUDGE_SEEDS) if arm else None, "stop": arm is None,
            "candidates_after_1": step1, "candidates_after_2": step2, "b1_b3_pass_count": counts,
            "decided_by": used, "trace": trace}


# --------------------------------------------------------------------- #
# TensorBoard (학습 분포의 경계 비율 vig/frac, 4.7 탐색 붕괴 감시)
# --------------------------------------------------------------------- #


def tb_dir(tbroot: Path, run: str) -> Path:
    cands = [p for p in Path(tbroot).glob(f"{run}_*") if p.is_dir() and p.name[len(run) + 1:].isdigit()]
    if len(cands) != 1:
        raise SystemExit(f"{tbroot}/{run}_<n> 이 하나여야 한다 (찾은 것: {[p.name for p in cands]})")
    return cands[0]


def tb_scalars(d: Path) -> dict[str, list[tuple[int, float]]]:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    ea = EventAccumulator(str(d), size_guidance={"scalars": 0})
    ea.Reload()
    tags = set(ea.Tags()["scalars"])
    return {t: [(int(e.step), float(e.value)) for e in ea.Scalars(t)] for t in TB_TAGS if t in tags}


def first_at(series, step: int):
    return next(((st, v) for st, v in series if st >= step), None)


def first_below(series, thr: float):
    return next((st for st, v in series if v < thr), None)


def tb_summary(series: dict, collapse_step: int) -> dict:
    """학습 기록 요약. 붕괴 판정 값은 `vig_frac_5m`(collapse_step 이상 첫 롤아웃의 vig/frac) 하나다. 나머지는 기록."""
    vig = series.get("vig/frac")
    if not vig:
        raise SystemExit("TensorBoard 에 vig/frac 이 없다 (vigilance 세계 학습이 아니다)")
    at = first_at(vig, collapse_step)
    if at is None:
        raise SystemExit(f"학습 기록이 {collapse_step:,} 스텝에 못 미친다 (마지막 {vig[-1][0]:,})")
    out = {"vig_frac_5m": at[1], "vig_frac_5m_step": at[0],
           "vig_frac": {k: (first_at(vig, n) or (None, None))[1]
                        for k, n in (("1M", 1_000_000), ("5M", collapse_step), ("10M", 10_000_000))},
           "vig_frac_last": vig[-1][1], "last_step": vig[-1][0],
           "first_below_5pct": first_below(vig, 0.05), "first_below_1pct": first_below(vig, 0.01),
           "vig_frac_max_after_5m": max(v for st, v in vig if st >= collapse_step)}
    for tag, key in (("act/speed_std", "speed_std"), ("act/vigilance_std", "vigilance_std")):
        s = series.get(tag)
        if s:
            v = np.array([x for _, x in s])
            out[key] = {"init": float(v[0]), "at_5m": (first_at(s, collapse_step) or (None, None))[1],
                        "last": float(v[-1]), "min": float(v.min()), "min_ratio": float(v.min() / v[0]) if v[0] else None}
    for tag, key in (("policy/vigilance_log_std", "vigilance_log_std"), ("policy/speed_log_std", "speed_log_std"),
                     ("act/vigilance_mean", "vigilance_act_mean")):
        s = series.get(tag)
        if s:
            out[key] = {"at_5m": (first_at(s, collapse_step) or (None, None))[1], "last": s[-1][1]}
    sp = out.get("speed_std")
    out["speed_std_below_10pct"] = bool(sp and sp["min_ratio"] is not None and sp["min_ratio"] < 0.1)   # 기록만
    return out


# --------------------------------------------------------------------- #
# precheck · checktrain · armargs · selected
# --------------------------------------------------------------------- #


def run_paths(a, arm: str, seed: int) -> list[Path]:
    run = run_name(arm, seed)
    res, ckpt, cache = Path(a.res), Path(a.ckpt), Path(a.cache)
    out = [ckpt / f"{run}.zip", ckpt / f"{run}.json", ckpt / f"{run}_10m.zip", res / f"diag_{run}",
           res / f"diag_{run}_stoch", res / f"diag_{run}.log", res / f"train_{run}.log", cache / run,
           cache / f"{run}_stoch", res / "s1_6b" / f"b67_{run}.json"]
    out += [p for p in Path(a.tb).glob(f"{run}_*") if p.name[len(run) + 1:].isdigit()]
    return out


def cmd_precheck(a) -> int:
    d = config_digest(load_v2_config(J.CONFIG))
    if d != J.DIGEST:
        raise SystemExit(f"configs/v2_2.yaml 의 config_digest {d} ≠ {J.DIGEST} — 세계 설정을 바꾸지 않는다")
    if tuned_ent_coef() != TUNED_ENT_COEF:
        raise SystemExit(f"configs/ppo_best.yaml 의 ent_coef {tuned_ent_coef()} ≠ 사전 등록 {TUNED_ENT_COEF}")
    seeds = tuple(sorted(a.seeds))
    if not a.smoke:
        if seeds == COMPARE_SEEDS:
            if sorted(a.arms) != sorted(ARMS):
                raise SystemExit(f"비교 학습은 두 팔 모두다 (--arms a b), 받은 값 {a.arms}")
        elif seeds == JUDGE_SEEDS:
            sel = selected_arm(a)
            if sel is None or a.arms != [sel]:
                raise SystemExit(f"판정 재실행은 compare.json 이 고른 팔 하나만 한다 (선택 {sel!r}, 받은 값 {a.arms})")
        else:
            raise SystemExit(f"학습 시드는 비교 {list(COMPARE_SEEDS)} 또는 판정 재실행 {list(JUDGE_SEEDS)} 이다 (받은 값 {seeds})")
    found = []
    for arm in a.arms:
        for s in a.seeds:
            found += [p for p in run_paths(a, arm, s) if p.exists()]
        if seeds == JUDGE_SEEDS or a.smoke:
            pre = ARMS[arm]["prefix"]
            found += [p for p in (Path(a.res) / f"diag_{pre}", Path(a.res) / "s1_6b" / f"stage1_6_{pre}.json")
                      if p.exists()]
    if found:
        raise SystemExit("이미 있다 — 기존 결과·체크포인트·캐시를 덮지 않는다:\n  " + "\n  ".join(map(str, found)))
    print(f"precheck 통과: config_digest {d}, ent_coef 튜닝값 {TUNED_ENT_COEF}, "
          f"팔 {a.arms} × 학습 시드 {list(a.seeds)} 의 산출물이 아직 없다")
    return 0


def cmd_checktrain(a) -> int:
    import yaml

    tuned = yaml.safe_load(PPO_BEST.read_text(encoding="utf-8"))["params"]
    errors, rows = [], []
    for arm in a.arms:
        A = ARMS[arm]
        for s in a.seeds:
            run = run_name(arm, s)
            p = Path(a.ckpt) / f"{run}.json"
            m = J.load(p)
            want = {"seed": int(s), "init": None, "ent_coef": A["ent_coef"], "ent_coef_source": A["ent_coef_source"],
                    "init_action_bias": A["init_action_bias"],
                    "init_action_bias_source": A["init_action_bias_source"], "gamma_source": "cli"}
            if not a.smoke:
                want.update(steps=TRAIN_STEPS, config_digest=J.DIGEST)
            for k, v in want.items():
                if m.get(k) != v:
                    errors.append(f"{run}: {k}={m.get(k)!r} 인데 {v!r} 이어야 한다")
            if abs(float(m.get("gamma", float("nan"))) - J.GAMMA) > 1e-12:
                errors.append(f"{run}: γ {m.get('gamma')} ≠ {J.GAMMA}")
            if int(m.get("actual_timesteps", 0)) < int(m.get("steps", 1)):
                errors.append(f"{run}: 실제 학습량 {m.get('actual_timesteps')} < {m.get('steps')}")
            for k in ("learning_rate", "clip_range", "n_epochs"):
                if float(m["ppo"][k]) != float(tuned[k]):
                    errors.append(f"{run}: {k} {m['ppo'][k]} ≠ 튜닝값 {tuned[k]}")
            if float(m["ppo"]["ent_coef"]) != A["ent_coef"]:
                errors.append(f"{run}: 모델 ent_coef {m['ppo']['ent_coef']} ≠ {A['ent_coef']}")
            if (m.get("v2") or {}).get("version") != "2.2":
                errors.append(f"{run}: 설정 version {(m.get('v2') or {}).get('version')!r} ≠ '2.2'")
            if not a.smoke:
                for q in (Path(a.ckpt) / f"{run}.zip", Path(a.ckpt) / f"{run}_10m.zip"):
                    if not q.exists():
                        errors.append(f"{run}: {q} 가 없다")
            ip = m.get("init_policy") or {}
            rows.append(f"  {run}: ent_coef {m.get('ent_coef')} ({m.get('ent_coef_source')}), 편향 "
                        f"{m.get('init_action_bias')} ({m.get('init_action_bias_source')}), 시작 경계 확률 "
                        f"{(ip.get('vigilance') or {}).get('vig_prob', float('nan')):.3f}, μ "
                        f"{(ip.get('vigilance') or {}).get('mu_mean', float('nan')):+.4f}, 걷기 "
                        f"{((ip.get('speed') or {}).get('gait_prob') or {}).get('walk', float('nan')):.3f}, "
                        f"{m.get('actual_timesteps'):,} 스텝, {m.get('elapsed_min')}분, digest {m.get('config_digest')}")
    print("\n".join(rows))
    if errors:
        raise SystemExit("학습 메타가 팔 정의와 다르다:\n  " + "\n  ".join(errors))
    print("checktrain 통과")
    return 0


def selected_arm(a) -> str | None:
    p = Path(a.res) / "s1_6b" / "compare.json"
    if not p.exists():
        raise SystemExit(f"{p} 가 없다 — 비교 집계(compare) 전이다")
    return json.loads(p.read_text(encoding="utf-8"))["selection"]["arm"]


def cmd_selected(a) -> int:
    print(selected_arm(a) or "")
    return 0


def cmd_armargs(a) -> int:
    print(" ".join(ARMS[a.arm]["train_args"]))
    return 0


# --------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------- #


def collect_arm(a, arm: str, seeds, cond_holder: list) -> dict:
    res = Path(a.res)
    det, stoch, tb, repro = {}, {}, {}, {}
    for s in seeds:
        run = run_name(arm, s)
        dd = res / f"diag_{run}"
        abl, seg = J.load(dd / "ablate.json"), J.load(dd / "c2seg_e2.json")
        sto = J.load(res / f"diag_{run}_stoch" / "ablate.json")
        if not cond_holder:
            cond = J.Cond(a.smoke, abl["meta"])
            cond_holder.append(cond)
        cond = cond_holder[0]
        S = cond.eval_seeds
        cond.check(abl, f"{run} ablate")
        cond.check(seg, f"{run} c2seg_e2")
        cond.check(sto, f"{run} stoch", mode="stochastic")
        sha = {d["meta"].get("model_sha1") for d in (abl, seg, sto)}
        model = Path(a.ckpt) / f"{run}.zip"
        if len(sha) != 1 or None in sha or (model.exists() and model_fingerprint(model) not in sha):
            raise SystemExit(f"{run}: 모델 sha1 이 결과마다 다르거나 체크포인트와 다르다 {sha}")
        J.check_const(seg, f"{run} C2-seg E2", J.E2_SEG["table"], J.E2_SEG["bins"], J.E2_SEG["dims"], J.E2_C2)
        c0 = J.rows_of(abl, "C0", S)
        if J.rows_of(seg, "C0", S) != c0:
            raise SystemExit(f"{run}: c2seg_e2 의 C0 가 ablate 의 C0 와 다르다")
        det[s] = {"C0": c0, SEG: J.rows_of(seg, "C2-seg", S), "C2": J.rows_of(seg, "C2", S)}
        stoch[s] = {"C0": J.rows_of(sto, "C0", S)}
        if not a.smoke:
            e2c2, e2seg = J.load(J.E2_C2_JSON), J.load(J.E2_SEG_JSON)
            repro[s] = {"C2 (E2 V0/c2)": J.same_rows(det[s]["C2"], J.rows_of(e2c2, "C2", S)),
                        "C2-seg-E2 (E2 V0/d0_95 a_allow)": J.same_rows(det[s][SEG], J.rows_of(e2seg, "C2-seg", S))}
        tb[s] = tb_summary(tb_scalars(tb_dir(Path(a.tb), run)), a.collapse_step)
        tb[s]["dir"] = str(tb_dir(Path(a.tb), run))
        tb[s]["model_sha1"] = next(iter(sha))
    return {"det": det, "stoch": stoch, "tb": tb, "repro": repro}


def level(by_seed: dict, col: str, seeds) -> dict:
    return stratified_bootstrap_ci(J.matrix(by_seed, "C0", col, seeds), stat=iqm, reps=J.REPS, seed=J.BOOT_SEED)


def summarize_arm(arm: str, got: dict, seeds) -> dict:
    det, stoch, tb = got["det"], got["stoch"], got["tb"]
    per_seed = {}
    for s in seeds:
        dm = {c: fmean(J.vec(det[s]["C0"], c)) for c in REC_COLS}
        sm = {c: fmean(J.vec(stoch[s]["C0"], c)) for c in REC_COLS}
        sig_tb = bool(not (tb[s]["vig_frac_5m"] >= COLLAPSE_FRAC))
        sig_det = bool(not (dm["vig_frac"] > 0))
        per_seed[s] = {"det": dm, "stoch": sm, "tb": tb[s],
                       "collapse": {"vig_frac_5m_below_1pct": sig_tb, "det_vig_frac_zero": sig_det,
                                    "signal": bool(sig_tb or sig_det)}}
    collapse = any(per_seed[s]["collapse"]["signal"] for s in seeds)
    lf = J.bundle_delta(det, SEG, "g_gamma", seeds)                      # Δ = C2-seg − C0
    learning_failure = bool(lf["ci_excludes_0"] and lf["delta_iqm"]["lo"] > 0)
    sizes = {}
    for mode, src in (("det", det), ("stoch", stoch)):
        sizes[mode] = {}
        for x in SIZE_CLAIMS:
            col, crit = J.PRIMARY[x]["col"], J.PRIMARY[x]["crit"]
            vals = {s: fmean(J.vec(src[s]["C0"], col)) for s in seeds}
            ok = {s: bool(np.isfinite(v) and v >= crit) for s, v in vals.items()}
            sizes[mode][x] = {"col": col, "crit": crit, "per_seed": vals, "pass_per_seed": ok,
                              "n_pass": int(sum(ok.values())), "n_seeds": len(seeds)}
    return {
        "arm": arm, **{k: ARMS[arm][k] for k in ("prefix", "what", "ent_coef", "init_action_bias", "train_args")},
        "seeds": list(seeds), "runs": [run_name(arm, s) for s in seeds],
        "per_seed": per_seed,
        "collapse": collapse, "collapse_seeds": [s for s in seeds if per_seed[s]["collapse"]["signal"]],
        "learning_failure": learning_failure,
        "learning_failure_delta": {"delta_seg_minus_c0": lf["delta_iqm"], "delta_mean": lf["delta_mean"],
                                   "t_seedmean": lf["t_seedmean"], "per_seed": lf["per_seed"]},
        "g_gamma_iqm": level(det, "g_gamma", seeds), "starve_rate_iqm": level(det, "starve_rate", seeds),
        "sizes": sizes, "n_pass": {x: sizes["det"][x]["n_pass"] for x in SIZE_CLAIMS},
        # 기록(선택에 쓰지 않는다)
        "record": {"c2_minus_c0_g_gamma": J.bundle_delta(det, "C2", "g_gamma", seeds)["delta_iqm"],
                   "predation_rate_iqm": level(det, "predation_rate", seeds),
                   "stoch_g_gamma_iqm": level(stoch, "g_gamma", seeds),
                   "stoch_starve_rate_iqm": level(stoch, "starve_rate", seeds),
                   "stoch_minus_det_g_gamma": fmean(J.matrix(stoch, "C0", "g_gamma", seeds)
                                                    - J.matrix(det, "C0", "g_gamma", seeds))},
    }


def cmd_compare(a) -> int:
    warnings.filterwarnings("ignore", message="All-NaN slice encountered", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message="Mean of empty slice", category=RuntimeWarning)
    out = Path(a.out) if a.out else Path(a.res) / "s1_6b" / "compare.json"
    if out.exists() and not a.overwrite:
        raise SystemExit(f"{out} 가 이미 있다 — 덮지 않는다(--overwrite 로만)")
    seeds = list(a.seeds)
    if not a.smoke and tuple(sorted(seeds)) != COMPARE_SEEDS:
        raise SystemExit(f"비교 학습 시드는 {list(COMPARE_SEEDS)} 다 (받은 값 {seeds})")
    holder: list = []
    if not a.smoke:
        e2c2, e2seg = J.load(J.E2_C2_JSON), J.load(J.E2_SEG_JSON)
        cond0 = J.Cond(False)
        cond0.check(e2c2, "E2 C2")
        cond0.check(e2seg, "E2 A-허용 C2-seg")
        J.check_const(e2c2, "E2 C2", J.E2_C2)
        J.check_const(e2seg, "E2 A-허용 C2-seg", J.E2_SEG["table"], J.E2_SEG["bins"], J.E2_SEG["dims"], J.E2_C2)
    got = {arm: collect_arm(a, arm, seeds, holder) for arm in ARMS}
    cond = holder[0]
    summ = {arm: summarize_arm(arm, got[arm], seeds) for arm in ARMS}
    GA = J.matrix(got["a"]["det"], "C0", "g_gamma", seeds)
    GB = J.matrix(got["b"]["det"], "C0", "g_gamma", seeds)
    g_diff = boot_diff_stat(GA, GB)
    sel = select_arm(summ, g_diff)
    data = {
        "generated": J.now(), "script": "python results/v2/_stage1_6b_compare.py " + " ".join(sys.argv[1:]),
        "prereg": "results/v2/s1_6b/PREREG.md", "smoke": bool(a.smoke),
        "condition": {"config": "configs/v2_2.yaml", "config_digest": cond.digest, "gamma": J.GAMMA,
                      "eval_seeds": [cond.eval_seeds[0], cond.eval_seeds[-1]], "n_eval_seeds": len(cond.eval_seeds),
                      "eval_steps": cond.eval_steps, "tail": cond.tail, "train_seeds": seeds,
                      "reps": J.REPS, "boot_seed": J.BOOT_SEED, "collapse_step": a.collapse_step,
                      "collapse_frac": COLLAPSE_FRAC},
        "arms": summ,
        "g_gamma_iqm_diff_a_minus_b": g_diff,
        "reproduction": {arm: got[arm]["repro"] for arm in ARMS} if not a.smoke else "생략(smoke)",
        "selection": sel,
    }
    save_json(out, clean(data))
    print(f"저장: {out}")
    summary(clean(data))
    return 0


def _f(v, spec=".3f") -> str:
    return "—" if v is None or not np.isfinite(float(v)) else format(float(v), spec)


def summary(d: dict) -> None:
    for arm, x in d["arms"].items():
        print(f"\n팔 {arm} ({x['what']}):")
        for s, p in x["per_seed"].items():
            dm, c = p["det"], p["collapse"]
            print(f"  s{s}: G_γ {_f(dm['g_gamma'])}  B1 {_f(dm['b1'])}  B2 {_f(dm['b2'])}  B3 {_f(dm['b3_truth'])}  "
                  f"아사율 {_f(dm['starve_rate'], '.5f')}  결정 경계 {_f(dm['vig_frac'], '.4f')}  "
                  f"5M vig/frac {_f(p['tb']['vig_frac_5m'], '.4f')}  붕괴 신호 {c['signal']}  "
                  f"| 확률 G_γ {_f(p['stoch']['g_gamma'])}")
        lf = x["learning_failure_delta"]["delta_seg_minus_c0"]
        g = x["g_gamma_iqm"]
        print(f"  G_γ IQM {_f(g['point'])} [{_f(g['lo'])}, {_f(g['hi'])}]  학습 실패 Δ(E2 C2-seg − C0) "
              f"{_f(lf['point'], '+.3f')} [{_f(lf['lo'], '+.3f')}, {_f(lf['hi'], '+.3f')}] → "
              f"{'학습 실패' if x['learning_failure'] else '아님'}  붕괴 {x['collapse']} {x['collapse_seeds']}  "
              f"크기 통과 {x['n_pass']}")
    gd = d["g_gamma_iqm_diff_a_minus_b"]
    print(f"\nG_γ IQM 차 A − B {_f(gd['point'], '+.3f')} [{_f(gd['lo'], '+.3f')}, {_f(gd['hi'], '+.3f')}]")
    print("선택:", "\n  ".join([""] + d["selection"]["trace"]))
    print("→", d["selection"]["arm"] or "없음(멈춤)")


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="1-6b 학습 실패 대응 비교 (PREREG: results/v2/s1_6b/PREREG.md)")
    p.add_argument("cmd", choices=["precheck", "checktrain", "compare", "selected", "armargs"])
    p.add_argument("--arms", nargs="+", choices=list(ARMS), default=list(ARMS), help="precheck·checktrain 의 팔")
    p.add_argument("--arm", choices=list(ARMS), default=None, help="armargs 의 팔")
    p.add_argument("--seeds", type=int, nargs="+", default=list(COMPARE_SEEDS), help="학습 시드 (기본 0 1 2)")
    p.add_argument("--res", default=str(REF), help="진단 결과·s1_6b 의 뿌리 (기본 results/v2)")
    p.add_argument("--ckpt", default=str(ROOT / "ckpt" / "v2"), help="체크포인트 디렉터리")
    p.add_argument("--cache", default=str(ROOT / "runs" / "v2_diag"), help="보정 표본 캐시 뿌리 (precheck)")
    p.add_argument("--tb", default=str(ROOT / "runs" / "v2"), help="TensorBoard 뿌리")
    p.add_argument("--out", default=None, help="compare 출력 JSON (기본 <res>/s1_6b/compare.json)")
    p.add_argument("--overwrite", action="store_true", help="compare 출력이 있으면 덮는다")
    p.add_argument("--smoke", action="store_true", help="도구 시험: 조건을 결과 meta 에서 읽고 재현·학습량 검사를 건너뛴다")
    p.add_argument("--collapse-step", type=int, default=COLLAPSE_STEP, help="붕괴 판정 시점 (--smoke 에서만 바꾼다)")
    a = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    if a.collapse_step != COLLAPSE_STEP and not a.smoke:
        raise SystemExit("--collapse-step 은 --smoke 에서만 바꾼다 (PREREG: 5,000,000)")
    if len(set(a.seeds)) != len(a.seeds) or len(set(a.arms)) != len(a.arms):
        raise SystemExit("--seeds·--arms 에 같은 값이 두 번 있다")
    if a.cmd == "armargs" and a.arm is None:
        raise SystemExit("armargs 는 --arm 이 필요하다")
    return {"precheck": cmd_precheck, "checktrain": cmd_checktrain, "compare": cmd_compare,
            "selected": cmd_selected, "armargs": cmd_armargs}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
