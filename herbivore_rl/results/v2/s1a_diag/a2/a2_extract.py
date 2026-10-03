"""S1-a 진단 A2 (학습 경과와 조기 신호) — 14모델의 학습 기록을 시간축으로 모은다 → a2/curves.json.

    # herbivore_rl/ 에서
    python results/v2/s1a_diag/a2/a2_extract.py

- 모델 14개(configs/v2_1.yaml, 관측 7·행동 5): v2_1_s0~2(--threads 3), v2_2r_t0_s20~25, v2_1c_s30~34(--threads 1)
- 라벨(stage1_close.md 8절 구분, 결과 뒤 기술): 좋음 9, 나쁨 4(t0_s24, v2_1c_s30·s31·s33), 경계 1(t0_s21)
- TB run 은 메타 command 의 --run-name 과 runs/v2/<run>_N 폴더를 맞춘다. 같은 이름 폴더가 여럿이면 메타 generated −
  elapsed_min 과 이벤트 파일 시각이 가장 가까운 것을 고른다(지금은 모두 _1 하나뿐이다)
- 읽는 것: TB 스칼라 전부(time/fps 포함, 분석에서는 뺀다), 메타 probe_history·r2_history, 결과 지표(G_γ 결정·아사율·
  같은 평가 시드 집합의 C2)
- 코어 코드는 고치지 않는다. 읽기만 한다.
"""

from __future__ import annotations

import glob
import json
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]          # herbivore_rl/
sys.path.insert(0, str(ROOT))

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator  # noqa: E402

CKPT = ROOT / "ckpt" / "v2"
RUNS = ROOT / "runs" / "v2"
RES = ROOT / "results" / "v2"

MODELS = (["v2_1_s0", "v2_1_s1", "v2_1_s2"]
          + [f"v2_2r_t0_s{s}" for s in range(20, 26)]
          + [f"v2_1c_s{s}" for s in range(30, 35)])
BAD = {"v2_2r_t0_s24", "v2_1c_s30", "v2_1c_s31", "v2_1c_s33"}
BORDER = {"v2_2r_t0_s21"}
# 같은 평가 시드 집합의 C2(결정 모드) — stage1_close.md 8절 구분 정의
C2_G = {"eval": 1.482, "explore": 1.217}


def label(m: str) -> str:
    return "bad" if m in BAD else ("border" if m in BORDER else "good")


def run_name(cmd: str) -> str:
    toks = shlex.split(cmd)
    return toks[toks.index("--run-name") + 1]


def pick_run_dir(run: str, meta: dict) -> tuple[Path, list[str]]:
    cands = sorted(p for p in RUNS.iterdir() if p.is_dir() and re.fullmatch(re.escape(run) + r"_\d+", p.name))
    if not cands:
        raise SystemExit(f"{run}: TB 폴더 없음")
    start = datetime.fromisoformat(meta["generated"]).timestamp() - 60.0 * float(meta["elapsed_min"])

    def ev_time(p: Path) -> float:
        f = sorted(p.glob("events.out.tfevents.*"))[0]
        return float(f.name.split(".")[3])

    best = min(cands, key=lambda p: abs(ev_time(p) - start))
    return best, [p.name for p in cands]


def outcomes() -> dict:
    out = {}
    for m in MODELS:
        if m.startswith("v2_2r_t0"):
            continue
        d = json.load(open(RES / f"diag_{m}" / "ablate.json", encoding="utf-8"))
        c = d["controls"]["C0"]["mean"]
        out[m] = {"seedset": "eval", "g_gamma": c["g_gamma"], "starve_rate": c["starve_rate"],
                  "p_stop_hungry": c.get("p_stop_hungry"), "src": f"diag_{m}/ablate.json C0"}
    h = json.load(open(RES / "v2_2r_explore" / "inv4" / "h234_eval.json", encoding="utf-8"))
    pm = h["per_model"]["T0"]["det"]
    for s in range(20, 26):
        out[f"v2_2r_t0_s{s}"] = {"seedset": "explore", "g_gamma": pm["g_gamma"][str(s)],
                                 "starve_rate": pm["starve_rate"][str(s)],
                                 "p_stop_hungry": None, "src": "v2_2r_explore/inv4/h234_eval.json per_model.T0.det"}
    for m, o in out.items():
        o["g_minus_c2"] = o["g_gamma"] - C2_G[o["seedset"]]
    return out


def main() -> int:
    res = {"models": MODELS, "labels": {m: label(m) for m in MODELS}, "runs": {}, "meta": {}, "tb": {},
           "probe": {}, "r2": {}, "outcome": outcomes()}
    for m in MODELS:
        meta = json.load(open(CKPT / f"{m}.json", encoding="utf-8"))
        run = run_name(meta["command"])
        d, cands = pick_run_dir(run, meta)
        res["runs"][m] = {"run": run, "dir": d.name, "candidates": cands}
        res["meta"][m] = {k: meta.get(k) for k in ("generated", "command", "elapsed_min", "seed", "actual_timesteps",
                                                "config_digest", "gamma")}
        res["meta"][m]["threads"] = int(shlex.split(meta["command"])[shlex.split(meta["command"]).index("--threads") + 1])
        res["meta"][m]["init_gait"] = meta["init_policy"]["speed"]["gait_prob"]
        res["probe"][m] = meta.get("probe_history") or []
        res["r2"][m] = meta.get("r2_history") or []
        f = sorted(d.glob("events.out.tfevents.*"))
        assert len(f) == 1, (m, f)
        ea = EventAccumulator(str(f[0]), size_guidance={"scalars": 0})
        ea.Reload()
        res["tb"][m] = {t: [[int(e.step), float(e.value)] for e in ea.Scalars(t)] for t in ea.Tags()["scalars"]}
        print(m, label(m), d.name, len(res["tb"][m]), "tags", len(res["tb"][m]["gait/stop"]), "rollouts",
              "probe", len(res["probe"][m]), flush=True)
    (HERE.parent / "curves.json").write_text(json.dumps(res), encoding="utf-8")
    print("저장", HERE.parent / "curves.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
