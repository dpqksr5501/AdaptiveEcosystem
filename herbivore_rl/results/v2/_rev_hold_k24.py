"""수정 제안서 5절 #3 (R1 출시 모드) — 해시·위상 표본기로 K24 를 다시 잰다 → results/v2/rev/hold_k24.{json,md}.

`Docs/RL_Policy/RL_V2_REVISION_PROPOSAL.md` 3.1 (가)·부록 B 의 K 실측은 순차 난수 표본기였고 모든 개체의 유지 시계가
t=0 에 함께 시작했다(저장소 밖 원형 REV/k24/k24lib.py). 이 스크립트는 저장소의 실제 표본기(`env_v2/rollout.py`
HoldLearned: 해시 u = U(H(404, seed, salt, key, col, block)), 개체별 위상, 리스폰 때 새 키)로 결정 모드와 K24 를 같은
조건에서 다시 재고, 부록 B 의 값과 버전별 우위 모드를 비교한다.

    # herbivore_rl/ 에서
    python results/v2/_rev_hold_k24.py run       # 롤아웃 960회(모델 8 × 모드 2 × 시드 60), 워커 16 → json + md
    python results/v2/_rev_hold_k24.py report    # json → md 만 다시

조건 (부록 B 와 같다):
- 모델: v2.1 = ckpt/v2/v2_1_s{0,1,2}.zip + configs/v2_1.yaml (config_digest f068496361f9),
        v2.2 = ckpt/v2/v2_2_s{0..4}.zip + configs/v2_2.yaml (1-6 모델, config_digest efc8f775f1e1)
- 모드: 결정({"kind": "learned"}) 대 유지 표본 K24({"mode": "hold", "hold_k": 24}, salt 0)
- 시드: 평가 10000~10019, 탐색 12000~12039 (diagnose_v2.EXPLORE_SEEDS, 10-03 R6). 5000스텝
- G_γ: γ 0.9916661555611042, 끝 ceil(5/(1−γ)) = 600스텝 제외, 앞 제외 0
- 모델 값 = 시드 평균. 버전 값 = 모델 평균. 짝지은 t(유지 − 결정)는 시드마다 모델 평균 차를 낸 쌍으로 낸다
  (diagnose_v2.mode_compare 와 같은 층). 모델별 t 는 그 모델의 시드 쌍이다
- 모드 선택(3.1 (가) 순서 3): 탐색 시드에서 G_γ 평균이 높은 모드. 평가 시드에서 고른 모드와 맞는지 센다(부록 B.3)
- B1 ≥ 0.3, B2 ≥ 0.1, B8 ≤ 0.5 는 모델별 평가 시드 평균으로 센다(부록 B.1 과 같다)
- 재현 검사: 결정 모드 평가 시드 행의 G_γ 를 1-3·1-6 진단 결과(results/v2/diag_<모델>/ablate.json C0)와 비트 단위로 맞춘다
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402

from diagnose_v2 import EXPLORE_SEEDS, config_digest, model_fingerprint, paired, save_json, t_pvalue  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import make_executor, public_row, run_specs, tail_steps  # noqa: E402

OUT = HERE.parent / "rev"
GAMMA = 0.9916661555611042
STEPS = 5000
HOLD_K = 24
WORKERS = 16
EVAL_SEEDS = list(range(10000, 10020))
SEED_SETS = {"eval": EVAL_SEEDS, "explore": list(EXPLORE_SEEDS)}
VERSIONS = {
    "v2.1": {"config": "configs/v2_1.yaml", "digest": "f068496361f9", "models": [f"v2_1_s{s}" for s in range(3)]},
    "v2.2": {"config": "configs/v2_2.yaml", "digest": "efc8f775f1e1", "models": [f"v2_2_s{s}" for s in range(5)]},
}
MODES = ("det", "hold24")
# 시드별로 남길 열 (원시 배열 제외). b8_vig 는 v2.2 만 있다
REC_COLS = ["g_gamma", "mean_return", "survival", "predation_rate", "starve_rate", "b1", "b2", "b8", "b8_cmd",
            "stop_frac", "walk_frac", "run_frac", "stop_frac_cmd", "vig_frac", "b8_vig"]
# 부록 B.3 (모델별 탐색 결정 / K24, 평가 결정 / K24). 표본기가 순차 난수였다
PROPOSAL = {
    "v2_1_s0": {"explore": (1.582, 1.319), "eval": (1.926, 1.626)},
    "v2_1_s1": {"explore": (1.682, 1.444), "eval": (1.867, 1.654)},
    "v2_1_s2": {"explore": (1.356, 1.019), "eval": (1.495, 1.279)},
    "v2_2_s0": {"explore": (0.095, 0.958), "eval": (0.022, 1.081)},
    "v2_2_s1": {"explore": (1.471, 1.191), "eval": (1.706, 1.428)},
    "v2_2_s2": {"explore": (-0.918, 0.707), "eval": (-0.861, 0.972)},
    "v2_2_s3": {"explore": (-0.402, 0.926), "eval": (-0.547, 1.204)},
    "v2_2_s4": {"explore": (-0.434, -0.069), "eval": (-0.455, 0.125)},
}
# 부록 B.1 (평가 시드): 모드별 B1 ≥ 0.3 · B2 ≥ 0.1 · B8 ≤ 0.5 모델 수와 B8 최댓값
PROPOSAL_COUNTS = {"v2.1": {"det": (2, 2, 3, 0.344), "hold24": (3, 3, 3, 0.482)},
                   "v2.2": {"det": (1, 4, 5, 0.232), "hold24": (5, 2, 5, 0.432)}}


def spec(model: str, mode: str) -> dict:
    s = {"kind": "learned", "model": str((ROOT / "ckpt" / "v2" / f"{model}.zip").resolve())}
    return {**s, "mode": "hold", "hold_k": HOLD_K} if mode == "hold24" else s


def fnum(v):
    v = float(v)
    return v if math.isfinite(v) else None


# --------------------------------------------------------------------- #
# 롤아웃
# --------------------------------------------------------------------- #


def run(a) -> dict:
    seeds = SEED_SETS["eval"] + SEED_SETS["explore"]
    meta = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "command": "python results/v2/_rev_hold_k24.py " + " ".join(sys.argv[1:]),
            "gamma": GAMMA, "tail": tail_steps(GAMMA), "head": 0, "steps": STEPS, "hold_k": HOLD_K, "salt": 0,
            "seed_sets": SEED_SETS, "workers": a.workers, "versions": {}}
    rows: dict[str, dict[str, dict[str, list[dict]]]] = {}
    t0 = time.time()
    ex = make_executor(a.workers)
    try:
        for ver, v in VERSIONS.items():
            cfg = load_v2_config(ROOT / v["config"])
            dig = config_digest(cfg)
            if dig != v["digest"]:
                raise SystemExit(f"{v['config']}: config_digest {dig} 가 기록된 {v['digest']} 와 다르다 — 세계가 바뀌었다")
            meta["versions"][ver] = {"config": v["config"], "config_digest": dig,
                                     "model_sha1": {m: model_fingerprint(ROOT / "ckpt" / "v2" / f"{m}.zip")
                                                    for m in v["models"]}}
            specs = {f"{m}|{mode}": spec(m, mode) for m in v["models"] for mode in MODES}
            res = run_specs(cfg, specs, seeds, STEPS, gamma=GAMMA, executor=ex)
            for name, rs in res.items():
                m, mode = name.split("|")
                pub = [public_row(r) for r in rs]
                rows.setdefault(m, {})[mode] = [{"seed": r["seed"], **{c: fnum(r[c]) for c in REC_COLS if c in r}}
                                                for r in pub]
            print(f"[{ver}] {len(specs)} 스펙 × {len(seeds)} 시드 ({time.time() - t0:.0f}s)", flush=True)
    finally:
        if ex is not None:
            ex.shutdown()
    meta["elapsed_s"] = round(time.time() - t0, 1)
    data = {"meta": meta, "per_seed": rows}
    data["summary"] = summarize(data)
    return data


# --------------------------------------------------------------------- #
# 집계
# --------------------------------------------------------------------- #


def col(rows: list[dict], c: str, seeds) -> np.ndarray:
    by = {r["seed"]: r.get(c) for r in rows}
    return np.array([np.nan if by[s] is None else by[s] for s in seeds], dtype=np.float64)


def tstat(diff_per_seed: np.ndarray) -> dict:
    d = np.asarray(diff_per_seed, dtype=np.float64)
    t = paired(d, np.zeros_like(d))
    t["p"] = t_pvalue(t["t"], len(d) - 1)
    t.pop("sig", None)                     # diagnose_v2.T_CRIT 은 자유도 19 값이라 40 시드에는 쓰지 않는다
    return t


def reproduce(model: str, det_eval: list[dict], meta: dict) -> float | None:
    """결정 모드 평가 시드 G_γ 와 진단 결과 C0 의 최대 절대 차 (같은 설정·모델·조건일 때만, 아니면 None)."""
    p = HERE.parent / f"diag_{model}" / "ablate.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    m = d["meta"]
    if (m.get("eval_seeds") != meta["seed_sets"]["eval"] or m.get("eval_steps") != meta["steps"]
            or m.get("gamma") != meta["gamma"] or m.get("tail") != meta["tail"] or int(m.get("head") or 0) != 0
            or (m.get("act_mode") or "deterministic") != "deterministic"
            or m.get("model_sha1") != model_fingerprint(ROOT / "ckpt" / "v2" / f"{model}.zip")):
        return None
    ref = col(d["per_seed"]["C0"], "g_gamma", m["eval_seeds"])
    return float(np.max(np.abs(ref - col(det_eval, "g_gamma", m["eval_seeds"]))))


def summarize(data: dict) -> dict:
    """시드별 행 → 모델·버전 집계. 시드 목록은 결과 meta 의 것을 쓴다."""
    rows, seed_sets = data["per_seed"], data["meta"]["seed_sets"]
    out = {"models": {}, "versions": {}}
    for ver, v in VERSIONS.items():
        vs = {}
        for sset, seeds in seed_sets.items():
            D = np.stack([col(rows[m]["det"], "g_gamma", seeds) for m in v["models"]])
            H = np.stack([col(rows[m]["hold24"], "g_gamma", seeds) for m in v["models"]])
            vs[sset] = {"det": float(D.mean()), "hold24": float(H.mean()), "diff": float((H - D).mean()),
                        "test": tstat((H - D).mean(0)),
                        "proposal": [float(np.mean([PROPOSAL[m][sset][k] for m in v["models"]])) for k in (0, 1)]}
        for m in v["models"]:
            mm = {}
            for sset, seeds in seed_sets.items():
                d, h = col(rows[m]["det"], "g_gamma", seeds), col(rows[m]["hold24"], "g_gamma", seeds)
                mm[sset] = {"det": float(d.mean()), "hold24": float(h.mean()), "test": tstat(h - d),
                            "pick": "hold24" if h.mean() > d.mean() else "det",
                            "proposal": list(PROPOSAL[m][sset])}
                for c in ("b1", "b2", "b8", "b8_cmd", "b8_vig", "vig_frac", "stop_frac_cmd"):
                    for mode in MODES:
                        x = col(rows[m][mode], c, seeds)
                        mm[sset][f"{c}_{mode}"] = float(np.nanmean(x)) if np.isfinite(x).any() else None
            mm["agree"] = mm["explore"]["pick"] == mm["eval"]["pick"]
            mm["reproduce_max_abs"] = reproduce(m, rows[m]["det"], data["meta"])
            out["models"][m] = mm
        ms = [out["models"][m]["eval"] for m in v["models"]]
        vs["counts_eval"] = {f"{mode}": {"b1_ge_0.3": sum(x[f"b1_{mode}"] >= 0.3 for x in ms),
                                         "b2_ge_0.1": sum(x[f"b2_{mode}"] >= 0.1 for x in ms),
                                         "b8_le_0.5": sum(x[f"b8_{mode}"] <= 0.5 for x in ms),
                                         "b8_max": max(x[f"b8_{mode}"] for x in ms)} for mode in MODES}
        vs["pick_explore"] = "hold24" if vs["explore"]["hold24"] > vs["explore"]["det"] else "det"
        vs["pick_eval"] = "hold24" if vs["eval"]["hold24"] > vs["eval"]["det"] else "det"
        vs["proposal_pick"] = "hold24" if vs["eval"]["proposal"][1] > vs["eval"]["proposal"][0] else "det"
        vs["proposal_counts_eval"] = PROPOSAL_COUNTS[ver]
        out["versions"][ver] = vs
    return out


# --------------------------------------------------------------------- #
# 보고서
# --------------------------------------------------------------------- #

MODE_KO = {"det": "결정", "hold24": "K24"}


def _t(test: dict) -> str:
    return f"{test['diff']:+.3f} (t {test['t']:+.2f}, p {test['p']:.3g})"


def report(data: dict) -> list[str]:
    s, meta = data["summary"], data["meta"]
    L = ["# R1 출시 모드 재측정 — 해시·위상 표본기 K24 (수정 제안서 5절 #3)", "",
         "| 버전 (모델 수) | 시드 | 결정 G_γ | K24 G_γ | K24 − 결정 (짝 t, p) | 부록 B 결정 / K24 | 고른 모드 |",
         "|---|---|---|---|---|---|---|"]
    for ver, vs in s["versions"].items():
        n = len(VERSIONS[ver]["models"])
        for sset, label in (("eval", "평가 10000~10019"), ("explore", "탐색 12000~12039")):
            x = vs[sset]
            L.append(f"| {ver} ({n}) | {label} | {x['det']:.3f} | {x['hold24']:.3f} | {_t(x['test'])} | "
                     f"{x['proposal'][0]:.3f} / {x['proposal'][1]:.3f} | "
                     f"{MODE_KO[vs['pick_' + sset]]} |")
    L += ["", "| 버전 | 모드 (평가 시드) | B1 ≥ 0.3 | B2 ≥ 0.1 | B8 ≤ 0.5 (최대) | 부록 B.1 B1 · B2 · B8 (최대) |",
          "|---|---|---|---|---|---|"]
    for ver, vs in s["versions"].items():
        n = len(VERSIONS[ver]["models"])
        for mode in MODES:
            c, pc = vs["counts_eval"][mode], vs["proposal_counts_eval"][mode]
            L.append(f"| {ver} | {MODE_KO[mode]} | {c['b1_ge_0.3']}/{n} | {c['b2_ge_0.1']}/{n} | "
                     f"{c['b8_le_0.5']}/{n} ({c['b8_max']:.3f}) | {pc[0]}/{n} · {pc[1]}/{n} · {pc[2]}/{n} ({pc[3]:.3f}) |")
    L += ["", "## 모델별 (G_γ 결정 / K24, 괄호는 부록 B.3)", "",
          "| 모델 | 탐색 | 평가 | K24 − 결정 탐색 (t) | K24 − 결정 평가 (t) | 탐색 선택 = 평가 선택 | B8 K24 (평가) "
          "| B1 / B2 K24 (평가) |",
          "|---|---|---|---|---|---|---|---|"]
    for m, mm in s["models"].items():
        ex, ev = mm["explore"], mm["eval"]
        L.append(f"| {m} | {ex['det']:.3f} / {ex['hold24']:.3f} ({ex['proposal'][0]:.3f} / {ex['proposal'][1]:.3f}) | "
                 f"{ev['det']:.3f} / {ev['hold24']:.3f} ({ev['proposal'][0]:.3f} / {ev['proposal'][1]:.3f}) | "
                 f"{ex['test']['diff']:+.3f} ({ex['test']['t']:+.2f}) | {ev['test']['diff']:+.3f} ({ev['test']['t']:+.2f}) | "
                 f"{MODE_KO[ex['pick']]} = {MODE_KO[ev['pick']]}: {'예' if mm['agree'] else '아니오'} | "
                 f"{ev['b8_hold24']:.3f} | {ev['b1_hold24']:.3f} / {ev['b2_hold24']:.3f} |")
    agree = sum(mm["agree"] for mm in s["models"].values())
    rep = [mm["reproduce_max_abs"] for mm in s["models"].values()]
    L += ["", "## 판정", ""]
    for ver, vs in s["versions"].items():
        same = vs["pick_eval"] == vs["proposal_pick"]
        L.append(f"- {ver}: 평가 시드 우위 모드 {MODE_KO[vs['pick_eval']]} (K24 − 결정 {vs['eval']['diff']:+.3f}), "
                 f"부록 B 는 {MODE_KO[vs['proposal_pick']]} "
                 f"({vs['eval']['proposal'][1] - vs['eval']['proposal'][0]:+.3f}) — "
                 + ("**같다**." if same else "**다르다.**")
                 + f" 탐색 시드로 고른 모드 {MODE_KO[vs['pick_explore']]}"
                 + (" (평가와 같다)." if vs["pick_explore"] == vs["pick_eval"] else " (평가와 다르다).")
                 + f" K24 B8 최대 {vs['counts_eval']['hold24']['b8_max']:.3f}"
                 + (" ≤ 0.5." if vs["counts_eval"]["hold24"]["b8_max"] <= 0.5 else " > 0.5 (위험 표의 K 재측정 신호)."))
    for ver, vs in s["versions"].items():
        parts = []
        for sset, label in (("eval", "평가"), ("explore", "탐색")):
            dm = [s["models"][m][sset]["hold24"] - s["models"][m][sset]["proposal"][1] for m in VERSIONS[ver]["models"]]
            parts.append(f"{label} {vs[sset]['hold24'] - vs[sset]['proposal'][1]:+.3f} (모델별 {min(dm):+.3f}~{max(dm):+.3f})")
        L.append(f"- {ver} K24 − 부록 B K24: " + ", ".join(parts) + ". 표본기(잡음 실현·위상)가 달라서 생기는 차이다.")
    L.append(f"- 모델 단위 탐색 선택 = 평가 선택: {agree}/{len(s['models'])}.")
    L.append("- 재현: 결정 모드 평가 시드 G_γ 가 진단 결과 C0 와 최대 "
             + (f"{max(x for x in rep if x is not None):.2e}" if any(x is not None for x in rep) else "비교 불가")
             + f" 차이 (비교한 모델 {sum(x is not None for x in rep)}/{len(rep)}). 결정 모드 값은 부록 B 와 같은 경로다.")
    L += ["", "## 조건", "",
          "- 표본기: `env_v2/rollout.py` HoldLearned (조향 4열 평균, speed·vigilance 열만 u = U(H(404, seed, 0, key, col, "
          f"⌊(tick + φ)/{meta['hold_k']}⌋)), φ = H(404, seed, 0, key, 0xFFFFFFFF) mod {meta['hold_k']}, "
          "key = 슬롯·2^32 + 리스폰 세대). seed = 평가·탐색 시드",
          f"- {meta['steps']}스텝, γ {meta['gamma']}, 끝 {meta['tail']}스텝 제외. 짝 t 는 시드마다 모델 평균 차"
          f"(평가 자유도 {len(meta['seed_sets']['eval']) - 1}, 탐색 {len(meta['seed_sets']['explore']) - 1}). "
          f"워커 {meta['workers']}, {meta.get('elapsed_s')}초",
          "- 설정: " + ", ".join(f"{ver} `{v['config']}` {v['config_digest']}" for ver, v in meta["versions"].items()),
          "- 부록 B 값은 순차 난수·동시 시작 표본기(REV/k24/k24lib.py)의 것이다. 결정 모드는 같은 경로라 같아야 한다",
          f"- 생성: {meta['generated']} · `{meta['command']}`"]
    return L


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=["run", "report"])
    p.add_argument("--workers", type=int, default=WORKERS)
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args(argv)
    out = Path(a.out)
    if a.cmd == "run":
        data = run(a)
        save_json(out / "hold_k24.json", data)
    else:
        data = json.loads((out / "hold_k24.json").read_text(encoding="utf-8"))
        data["summary"] = summarize(data)
        save_json(out / "hold_k24.json", data)
    lines = report(data)
    (out / "hold_k24.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"저장: {out / 'hold_k24.json'}\n      {out / 'hold_k24.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
