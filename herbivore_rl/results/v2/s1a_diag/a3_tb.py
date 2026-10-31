"""A3 진단 보조: TensorBoard 학습 곡선에서 forage·cover·정지·에너지 궤적을 모델 14개에 대해 뽑는다 (학습 없음).

실행(herbivore_rl 에서): python results/v2/s1a_diag/a3_tb.py
산출: results/v2/s1a_diag/a3_tb.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

H = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "a3_tb.json"

MODELS = {
    "v2_1_s0": "good", "v2_1_s1": "good", "v2_1_s2": "good",
    "v2_2r_t0_s20": "good", "v2_2r_t0_s21": "border", "v2_2r_t0_s22": "good", "v2_2r_t0_s23": "good",
    "v2_2r_t0_s24": "bad", "v2_2r_t0_s25": "good",
    "v2_1c_s30": "bad", "v2_1c_s31": "bad", "v2_1c_s32": "good", "v2_1c_s33": "bad", "v2_1c_s34": "good",
}
TAGS = ["act/forage_mean", "act/cohesion_mean", "act/cover_mean", "act/speed_mean", "gait/stop", "gait/walk",
        "gait/run", "world/mean_energy", "world/in_cover_frac", "rollout/reward_per_step",
        "policy/forage_log_std", "policy/speed_log_std", "train/explained_variance", "train/value_loss"]
MARKS = [0.25e6, 0.5e6, 1e6, 2e6, 3e6, 5e6, 10e6, 15e6, 20e6]


def run_dir(name: str) -> Path:
    return H / "runs" / "v2" / f"{name}_1"


def main() -> None:
    out = {"generated_by": "results/v2/s1a_diag/a3_tb.py", "marks": MARKS, "models": {}}
    for name, cls in MODELS.items():
        ea = EventAccumulator(str(run_dir(name)), size_guidance={"scalars": 0})
        ea.Reload()
        tags = set(ea.Tags()["scalars"])
        rec = {"class": cls, "tags": {}}
        for t in TAGS:
            if t not in tags:
                continue
            ev = ea.Scalars(t)
            st = np.array([e.step for e in ev], dtype=np.float64)
            va = np.array([e.value for e in ev], dtype=np.float64)
            # 표시 지점 근처(±250k) 평균. 첫 지점은 그 앞 전부
            vals = []
            for m in MARKS:
                sel = (st > m - 250e3) & (st <= m + 250e3) if m > 0.5e6 else (st <= m)
                vals.append(float(va[sel].mean()) if sel.any() else None)
            rec["tags"][t] = {"n": int(len(ev)), "at_marks": vals, "first": float(va[0]), "last": float(va[-1]),
                              "first_step": int(st[0])}
        out["models"][name] = rec
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # 화면 요약
    for t in ["act/forage_mean", "act/cover_mean", "gait/stop", "world/mean_energy", "rollout/reward_per_step"]:
        print(f"== {t}  marks(M) {[m/1e6 for m in MARKS]}")
        for name, rec in out["models"].items():
            r = rec["tags"].get(t)
            if r:
                print(f"{name:14s} {rec['class']:6s} first {r['first']:.3f}@{r['first_step']}  " +
                      " ".join("  -  " if v is None else f"{v:.3f}" for v in r["at_marks"]))


if __name__ == "__main__":
    main()
