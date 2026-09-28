"""§7 비교 평가.

    python evaluate.py

§3.5: 평가 시드는 **10000~10019** 다. 학습·튜닝에 쓴 0~999 와 겹치지 않는다.
§7.1: 시드마다 `World(cfg, seeds=[s])` 를 새로 만들고, 학습 정책은 `deterministic=True`.

산출물 (§7.3):
    results/compare.csv   정책 × 시드 × §7.2 열
    results/compare.md    평균 ± 표준편차. 차이가 표준편차 안이면 "차이 없음" 명시

§0: "규칙이 이겨도 실패가 아니다. 측정 결과 자체가 산출물이다."
어느 쪽이 이겼든 그대로 적는다 (§7.4).
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import csv
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from env.config import load_config
from env.rollout import STAT_COLUMNS, run_policy, std_of

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

# §7.2 열 중 성능 지표 — 우열을 말할 수 있다.
HIGHER_IS_BETTER = {"mean_return", "survival", "repro"}
LOWER_IS_BETTER = {"predation_rate"}
# 나머지는 **행동 지표**다. 크다고 좋은 게 아니라 "어떻게 행동하는가"를 기술할 뿐이다.
# 여기에 승패를 붙이면 읽는 사람을 오도한다.

# 대응표본 t, 자유도 19, 양측 5%
T_CRIT = 2.093


def eval_seeds(cfg) -> list[int]:
    lo, hi = cfg.eval_seeds
    return list(range(lo, hi))


def welch_paired(a: np.ndarray, b: np.ndarray):
    """시드를 짝지은 차이. 같은 세계에서 두 정책을 재므로 대응표본이 맞다."""
    d = a - b
    n = len(d)
    sd = d.std(ddof=1)
    se = sd / np.sqrt(n) if n > 1 else float("nan")
    t = d.mean() / se if se > 0 else float("nan")
    return d.mean(), sd, se, t


def write_csv(path: Path, rows_by_policy: dict[str, list[dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "seed"] + STAT_COLUMNS)
        for name, rows in rows_by_policy.items():
            for r in rows:
                w.writerow([name, r["seed"]] + [f"{r[c]:.6f}" for c in STAT_COLUMNS])


def write_md(path: Path, cfg, args, rows_by_policy: dict[str, list[dict]],
             primary: tuple[str, str]) -> None:
    """§7.3 — 평균 ± 표준편차 표. 차이가 표준편차 안이면 '차이 없음' 명시."""
    seeds = eval_seeds(cfg)
    means = {k: {c: float(np.mean([r[c] for r in v])) for c in STAT_COLUMNS}
             for k, v in rows_by_policy.items()}
    stds = {k: std_of(v) for k, v in rows_by_policy.items()}
    a_name, b_name = primary
    A = {c: np.array([r[c] for r in rows_by_policy[a_name]]) for c in STAT_COLUMNS}
    B = {c: np.array([r[c] for r in rows_by_policy[b_name]]) for c in STAT_COLUMNS}

    L = []
    L.append("# §7 비교 평가 — 학습 정책 vs Utility AI\n")
    L.append("> 자동 생성: `python evaluate.py`. 손으로 고치지 말 것.\n")
    L.append(f"- 생성: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
             f" (python {platform.python_version()})")
    L.append(f"- 시드: **{seeds[0]}~{seeds[-1]}** ({len(seeds)}개) — §3.5 평가 대역."
             " 학습·튜닝(0~999)과 겹치지 않는다.")
    L.append(f"- 스텝: {args.steps} / 시드")
    L.append(f"- 학습 정책: `{args.model}` (§7.1 `deterministic=True`)")
    L.append(f"- 비교군: `configs/utility_best.yaml` (§5.2 튜닝 결과)\n")

    def row(c, X, Y, xn, yn):
        md, sd, se, t = welch_paired(X[c], Y[c])
        # §7.3 의 기준: "차이가 표준편차 안이면 '차이 없음' 명시"
        spec_same = not np.isfinite(t) or abs(md) < sd
        sig = np.isfinite(t) and abs(t) > T_CRIT
        if c in HIGHER_IS_BETTER:
            better = (xn if md > 0 else yn) if sig else None
        elif c in LOWER_IS_BETTER:
            better = (xn if md < 0 else yn) if sig else None
        else:
            better = None   # 행동 지표 — 우열이 아니다
        note = ("성능: " + (f"**{better} 우세**" if better else "유의차 없음")
                if c in HIGHER_IS_BETTER or c in LOWER_IS_BETTER
                else "행동 지표 (우열 아님)")
        return (f"| `{c}` | {means[xn][c]:.4f} ± {stds[xn][c]:.4f} "
                f"| {means[yn][c]:.4f} ± {stds[yn][c]:.4f} "
                f"| {md:+.4f} ± {sd:.4f} | {t:+.2f} "
                f"| {'예' if sig else '아니오'} "
                f"| {'차이 없음' if spec_same else '차이 있음'} | {note} |")

    L.append(f"## 1. {a_name} vs {b_name}\n")
    L.append(f"| 열 | {a_name} | {b_name} | 차이 (짝지음) | t | 유의 | §7.3 판정 | 비고 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c in STAT_COLUMNS:
        L.append(row(c, A, B, a_name, b_name))
    L.append("")
    L.append("- ± 는 **시드 간 표준편차**다. 시드마다 세계가 완전히 다르므로 크다.")
    L.append("- '차이 (짝지음)' 은 같은 시드끼리 뺀 값이다. 세계 난이도가 상쇄되므로"
             " 이쪽이 정책 차이를 훨씬 잘 본다.")
    L.append(f"- **t** 는 대응표본 t 통계량. |t| > {T_CRIT} 면 양측 5% 에서 유의하다"
             f" (자유도 {len(seeds) - 1}).")
    L.append("- **§7.3 판정** 은 사양서가 정한 기준(|차이| < 차이의 표준편차 → '차이 없음')을"
             " 그대로 적용한 것이다. n=20 대응표본에서는 t 검정보다 보수적이라"
             " 유의한 차이도 '차이 없음' 으로 나올 수 있다 — 두 열을 같이 봐야 한다.")
    L.append("- 행동 지표(`cohesion_mean`, `flee_dist_*`, `cover_frac`, `react_*`)에는"
             " 우열을 붙이지 않는다. 크다고 좋은 값이 아니라 **어떻게 행동하는가**의 기술이다.\n")

    # --- 참고 모델 비교 ---
    for name in rows_by_policy:
        if name in (a_name, b_name, "random"):
            continue
        C = {c: np.array([r[c] for r in rows_by_policy[name]]) for c in STAT_COLUMNS}
        L.append(f"### 1.{list(rows_by_policy).index(name)} 참고: {name} vs {b_name}\n")
        L.append(f"| 열 | {name} | {b_name} | 차이 (짝지음) | t | 유의 | §7.3 판정 | 비고 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for c in ("mean_return", "survival", "repro", "predation_rate"):
            L.append(row(c, C, B, name, b_name))
        L.append("")

    # --- 전체 정책 요약 ---
    if len(rows_by_policy) > 2:
        L.append("## 2. 전체 정책 요약\n")
        L.append("| 정책 | " + " | ".join(f"`{c}`" for c in STAT_COLUMNS) + " |")
        L.append("|---" * (len(STAT_COLUMNS) + 1) + "|")
        for name in rows_by_policy:
            L.append(f"| {name} | "
                     + " | ".join(f"{means[name][c]:.3f}" for c in STAT_COLUMNS) + " |")
        L.append("")

    # --- 결론 (§7.4: 어느 쪽이 이겼든 그대로 적는다) ---
    md_ret, sd_ret, se_ret, t_ret = welch_paired(A["mean_return"], B["mean_return"])
    L.append("## 3. 결론\n")
    if abs(t_ret) <= T_CRIT:
        L.append(f"**`mean_return` 에서 두 정책은 구별되지 않는다.** 짝지은 차이"
                 f" {md_ret:+.2f} ± {sd_ret:.2f}, t={t_ret:+.2f} (임계 ±{T_CRIT}).")
    else:
        winner = a_name if md_ret > 0 else b_name
        L.append(f"**`mean_return` 에서 {winner} 가 앞선다.** 짝지은 차이"
                 f" {md_ret:+.2f} ± {sd_ret:.2f}, t={t_ret:+.2f}.")

    same_return = abs(t_ret) <= T_CRIT

    # 바닥선 대비 — 비교가 의미 있는 범위인지
    if "random" in rows_by_policy:
        rnd = means["random"]["mean_return"]
        L.append("")
        tail = (" 즉 두 방식 모두 '학습된 행동'을 하고 있고, 그럼에도 갈리지 않는 것은"
                " 그 위의 여지가 좁기 때문이다."
                if same_return else
                " 즉 두 방식 모두 무작위보다 훨씬 낫고, 그 위에서 다시 학습 정책이 앞선다.")
        L.append(f"둘 다 무작위 정책({rnd:.1f})은 크게 앞선다 —"
                 f" {a_name} {means[a_name]['mean_return']:.1f},"
                 f" {b_name} {means[b_name]['mean_return']:.1f}." + tail)

    # 행동 차이는 유의한가 — 적응성은 있는데 성능으로 안 이어지는지 보기 위해
    beh = [c for c in STAT_COLUMNS
           if c not in HIGHER_IS_BETTER and c not in LOWER_IS_BETTER]
    sig_beh = [c for c in beh
               if np.isfinite(welch_paired(A[c], B[c])[3])
               and abs(welch_paired(A[c], B[c])[3]) > T_CRIT]
    if sig_beh:
        L.append("")
        why = (" 두 정책이 같은 점수를 서로 다른 방식으로 낸다는 뜻이다."
               if same_return else
               " 점수 차이가 행동 차이에서 온다는 뜻이다.")
        L.append(f"**행동도 유의하게 다르다** — {', '.join(f'`{c}`' for c in sig_beh)}." + why)
    L.append("")
    L.append("§0: \"규칙이 이겨도 실패가 아니다. 측정 결과 자체가 산출물이다.\"")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="§7 비교 평가")
    p.add_argument("--steps", type=int, default=5000, help="§7.1 스텝 5000")
    p.add_argument("--model", default=str(ROOT / "ckpt" / "final.zip"))
    # §11-B 결정으로 final.zip 은 2M 모델이다. 대조군으로 폐기된 10M 모델을 같이 잰다 —
    # "왜 2M 인가" 의 근거가 보고서 안에 남아야 한다.
    p.add_argument("--extra-model", default=str(ROOT / "ckpt" / "final_10m_superseded.zip"),
                   help="참고용 추가 모델. 없으면 건너뛴다")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--config", default=None)
    p.add_argument("--out", default=str(RESULTS))
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    seeds = eval_seeds(cfg)
    print(f"§3.5 평가 시드 {seeds[0]}~{seeds[-1]} ({len(seeds)}개) × {args.steps} 스텝")

    specs = {
        "learned": {"kind": "learned", "model": args.model},
        "utility": {"kind": "utility"},
    }
    extra = Path(args.extra_model) if args.extra_model else None
    if extra and extra.exists() and extra.resolve() != Path(args.model).resolve():
        specs[f"learned({extra.stem})"] = {"kind": "learned", "model": str(extra)}
    # 바닥선 — 비교가 의미 있는 범위인지 보려면 필요하다
    specs["random"] = {"kind": "random", "seed": 0}

    rows_by_policy = {}
    for name, spec in specs.items():
        rows, mean = run_policy(cfg, spec, seeds, args.steps, args.workers)
        rows_by_policy[name] = rows
        print(f"  {name:22s} mean_return={mean['mean_return']:8.2f} "
              f"survival={mean['survival']:7.1f} repro={mean['repro']:5.2f} "
              f"pred_rate={mean['predation_rate']:.5f}")

    out = Path(args.out)
    write_csv(out / "compare.csv", rows_by_policy)
    write_md(out / "compare.md", cfg, args, rows_by_policy, ("learned", "utility"))
    print(f"\n저장: {out/'compare.csv'}")
    print(f"      {out/'compare.md'}")
    print("영상은 `python replay.py --policy utility` / `--policy learned` (§7.3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
