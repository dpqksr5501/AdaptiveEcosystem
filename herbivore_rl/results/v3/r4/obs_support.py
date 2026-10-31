"""v3 R4 관측이 R1b 학습 범위 안인가 (사전 등록 results/v3/r4/PREREG.md 2-4절, 학습 전 확인 — 판정 아님).

    # herbivore_rl/ 에서
    python results/v3/r4/obs_support.py          # → results/v3/r4/obs_support.json·.md

R1b 학습 세계(configs/v3_r1.yaml, 학습 시드 풀 [0, 1000) 에서 고른 12개 × 2000스텝, 두뇌 R1b argmax — 얼기 포함 목록)와 R4 학습 세계
(configs/v3_r4_train.yaml, 지역 셋 × 학습 시드 32000~32003 × 3000스텝, 두뇌 R1b-F argmax — 학습 시작점)의 산 사슴-스텝 관측 18칸을 모아 칸마다 견준다:
R1b 쪽 최솟값·최댓값·0.1%·99.9% 분위, R4 쪽 최솟값·최댓값, R4 표본 가운데 R1b [최솟값, 최댓값] 밖 몫(학습 범위 밖)과 [0.1%, 99.9%] 밖 몫.
칸 하나라도 범위 밖 몫이 0.1% 를 넘으면 표에 '밖'으로 적는다(보고만 — 학습을 막지 않는다. 이어 배우기가 그 칸의 새 값을 배운다).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402
import numpy as np  # noqa: E402

R1_CFG = ROOT / "configs" / "v3_r1.yaml"
R4_CFG = ROOT / "configs" / "v3_r4_train.yaml"
MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
R1_SEEDS = tuple(range(0, 1000, 90))[:12]
R4_SEEDS = (32000, 32001, 32002, 32003)
OUT = HERE.parent


def collect(cfg, seed: int, steps: int) -> np.ndarray:
    from env_v2 import rollout as ro
    from env_v2.world import World

    w = World(cfg, seeds=[int(seed)])
    pol = ro.build_policy({"kind": "rep_learned", "path": str(MODEL)}, int(seed))
    ro.forward_bind(pol, w)
    out = []
    for _ in range(steps):
        o = w.observe()
        out.append(o if w.alive is None else o[w.alive])
        w.step(np.asarray(pol(o), dtype=np.float64))
    return np.concatenate(out).astype(np.float64)


def _job(args):
    which, region, seed, steps = args
    from env_v2.config import load_v2_config

    if which == "r1":
        return which, region, collect(load_v2_config(R1_CFG), seed, steps)
    from env_v2.vec_env import region_configs, region_mix_params

    cfg = load_v2_config(R4_CFG)
    rm = region_mix_params(cfg.v2["train"]["region_mix"], cfg)
    return which, region, collect(region_configs(cfg, rm)[region], seed, steps)


def main() -> int:
    from concurrent.futures import ProcessPoolExecutor

    from env_v2.config import load_v2_config
    from env_v2.world import World

    names = list(World(load_v2_config(R4_CFG), seeds=[R4_SEEDS[0]]).obs_names)
    if names != list(World(load_v2_config(R1_CFG), seeds=[R1_SEEDS[0]]).obs_names):
        raise SystemExit("두 세계의 관측 이름이 다르다")
    regions = ("Barren", "Forest", "Highland")
    jobs = [("r1", None, s, 2000) for s in R1_SEEDS] + [("r4", r, s, 3000) for r in regions for s in R4_SEEDS]
    with ProcessPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(_job, jobs))
    r1 = np.concatenate([x for w, _, x in res if w == "r1"])
    r4 = {r: np.concatenate([x for w, g, x in res if w == "r4" and g == r]) for r in regions}
    lo, hi = r1.min(0), r1.max(0)
    q_lo, q_hi = np.quantile(r1, 0.001, axis=0), np.quantile(r1, 0.999, axis=0)
    rows = []
    for j, nm in enumerate(names):
        row = dict(slot=j, name=nm, r1_min=float(lo[j]), r1_max=float(hi[j]), r1_q001=float(q_lo[j]), r1_q999=float(q_hi[j]))
        for r in regions:
            x = r4[r][:, j]
            row[r] = dict(min=float(x.min()), max=float(x.max()), out_range=float(((x < lo[j] - 1e-9) | (x > hi[j] + 1e-9)).mean()),
                          out_q=float(((x < q_lo[j] - 1e-9) | (x > q_hi[j] + 1e-9)).mean()))
        row["outside"] = any(row[r]["out_range"] > 0.001 for r in regions)
        rows.append(row)
    meta = dict(r1_config=str(R1_CFG.relative_to(ROOT)), r4_config=str(R4_CFG.relative_to(ROOT)), model=str(MODEL.relative_to(ROOT)),
                r1_seeds=list(R1_SEEDS), r1_steps=2000, r4_seeds=list(R4_SEEDS), r4_steps=3000, r1_samples=int(len(r1)),
                r4_samples={r: int(len(v)) for r, v in r4.items()})
    (OUT / "obs_support.json").write_text(json.dumps(dict(meta=meta, slots=rows), ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# R4 관측이 R1b 학습 범위 안인가 (results/v3/r4/obs_support.py, 학습 전 확인 — 판정 아님)", "",
          f"- R1b 학습 세계 `{meta['r1_config']}` 시드 {list(R1_SEEDS)} × 2000스텝(R1b argmax), 산 사슴-스텝 {len(r1):,}개",
          f"- R4 학습 세계 `{meta['r4_config']}` 지역 셋 × 시드 {list(R4_SEEDS)} × 3000스텝(R1b-F argmax, 학습 보충 켬), 지역마다 "
          + ", ".join(f"{r} {len(v):,}" for r, v in r4.items()), "",
          "'밖 몫' = R4 표본 가운데 R1b 표본 [최솟값, 최댓값] 밖. '분위 밖' = R1b [0.1%, 99.9%] 분위 밖.", "",
          "| 칸 | 이름 | R1b 범위 | R1b 0.1~99.9% | " + " | ".join(f"{r} 범위 · 밖 몫 · 분위 밖" for r in regions) + " | 판단 |",
          "|---|---|---|---|" + "---|" * len(regions) + "---|"]
    for row in rows:
        cells = [f"{row[r]['min']:.3f}~{row[r]['max']:.3f} · {100 * row[r]['out_range']:.2f}% · {100 * row[r]['out_q']:.2f}%" for r in regions]
        md.append(f"| {row['slot']} | {row['name']} | {row['r1_min']:.3f}~{row['r1_max']:.3f} | {row['r1_q001']:.3f}~{row['r1_q999']:.3f} | "
                  + " | ".join(cells) + f" | {'**밖**' if row['outside'] else '안'} |")
    (OUT / "obs_support.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
