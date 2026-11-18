"""R10 평가 — 처음 보는 맵에서 배운 두뇌와 규칙 두뇌를 같은 조건으로 (0 단계 사양 10 절 '작은 확인').

    python -X utf8 results/v3/r10/eval_r10.py --only deer wolf boar --flat --brain deer=ckpt/r10/small/deer_5000000.npz
    python -X utf8 results/v3/r10/eval_r10.py --only deer wolf boar --flat                      # 모두 규칙 두뇌 (잣대)

- 맵: 점검 시드(60000~60999)만. 학습 시드·시험 시드는 쓰지 않는다. 되살리기 없음(train=False).
- 종마다: 1,000 개체-결정당 물려 죽음·굶어 죽음·물에서 죽음, 평균 기운, 먹은 결정 몫, (물 수 있는 종) 1,000 개체-결정당 죽인 수.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

from r10 import contract as C  # noqa: E402
from r10 import mapgen as G  # noqa: E402
from r10 import policy as P  # noqa: E402
from r10 import rule_brain as RB  # noqa: E402
from r10 import senses as O  # noqa: E402
from r10 import species as S  # noqa: E402
from r10 import world as W  # noqa: E402


def run(cards: dict, brains: dict, seeds: list, decisions: int, n_each: int, overrides: dict | None, world_seed: int,
        sample: bool = False) -> dict:
    ids = sorted(cards)
    maps = [G.make_map(s, "check", overrides) for s in seeds]
    ros = [W.Roster([(cards[s], n_each, n_each) for s in ids]) for _ in maps]
    w = W.World(maps, ros, slots=n_each * len(ids), seed=world_seed, train=False)
    o = O.observe(w)
    rng = np.random.default_rng(world_seed + 1)
    alive_dec = Counter()
    eat_dec = Counter()
    e_sum = defaultdict(float)
    start = Counter(ids[w.sp[i]] for i in np.nonzero(w.alive)[0])
    for _ in range(decisions):
        a = np.full(w.N, C.A_WATCH, np.int64)
        for si, sid in enumerate(ids):
            idx = np.nonzero(w.alive & (w.sp == si))[0]
            if len(idx) == 0:
                continue
            wts = brains.get(sid)
            a[idx] = (P.sample_np(wts, o[idx], rng) if sample else P.act_np(wts, o[idx])) if wts is not None else RB.decide(o[idx])
            alive_dec[sid] += len(idx)
            eat_dec[sid] += int((a[idx] == C.A_EAT).sum())
            e_sum[sid] += float(w.E[idx].sum())
        w.step(a)
        o = O.observe(w)
    deaths = defaultdict(Counter)
    kills = Counter()
    uid_sp = {}
    for d in w.events["deaths"]:
        deaths[ids[d[3]]][d[4]] += 1
    killer_sp = {}
    for i in range(w.N):
        if w.sp[i] >= 0:
            killer_sp[int(w.uid[i])] = ids[w.sp[i]]
    for d in w.events["deaths"]:
        if d[5] is not None and d[4] == "bitten":
            kills[killer_sp.get(d[5], "?")] += 1
    out = {}
    for sid in ids:
        n = max(alive_dec[sid], 1)
        out[sid] = {"start": start[sid], "end": int((w.alive & (w.sp == ids.index(sid))).sum()), "animal_decisions": alive_dec[sid],
                    "bitten_per_k": round(1000 * deaths[sid]["bitten"] / n, 3), "starved_per_k": round(1000 * deaths[sid]["starved"] / n, 3),
                    "water_per_k": round(1000 * deaths[sid]["out_of_water"] / n, 3), "mean_E": round(e_sum[sid] / n, 3),
                    "eat_share": round(eat_dec[sid] / n, 3), "kills_per_k": round(1000 * kills[sid] / n, 3),
                    "births": sum(b[3] for b in w.events["births"] if True) if False else None}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cards", default=str(S.SPECIES_DIR))
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--brain", nargs="*", default=[], help="종=npz")
    ap.add_argument("--flat", action="store_true")
    ap.add_argument("--seeds", type=int, nargs=2, default=[60000, 60016], help="점검 시드 [하, 상)")
    ap.add_argument("--decisions", type=int, default=1350, help="결정 수 (1,350 ≈ 하루 반)")
    ap.add_argument("--n-each", type=int, default=6)
    ap.add_argument("--world-seed", type=int, default=7)
    ap.add_argument("--sample", action="store_true", help="배운 두뇌를 학습 때처럼 확률로 뽑기 (기본: 가장 높은 칸)")
    ap.add_argument("--out", default=None, help="결과 JSON")
    a = ap.parse_args(argv)
    cards = S.load_all(a.cards)
    if a.only:
        cards = {k: v for k, v in cards.items() if k in set(a.only)}
    brains = {}
    for spec in a.brain:
        sid, _, path = spec.partition("=")
        brains[sid] = P.load_brain(path)
    overrides = {"shape": "flat", "water": "none"} if a.flat else None
    res = run(cards, brains, list(range(a.seeds[0], a.seeds[1])), a.decisions, a.n_each, overrides, a.world_seed, a.sample)
    head = f"두뇌 {({k: Path(v).name for k, v in (s.partition('=')[::2] for s in a.brain)}) or '모두 규칙'} · 맵 {a.seeds} · {a.decisions} 결정{' · 확률 뽑기' if a.sample else ''}"
    print(head)
    print(f"{'종':10s} {'시작':>4s} {'끝':>4s} {'물림/k':>7s} {'굶음/k':>7s} {'물/k':>6s} {'기운':>5s} {'먹기몫':>6s} {'죽임/k':>7s}")
    for sid, r in res.items():
        print(f"{sid:10s} {r['start']:4d} {r['end']:4d} {r['bitten_per_k']:7.3f} {r['starved_per_k']:7.3f} {r['water_per_k']:6.3f} "
              f"{r['mean_E']:5.2f} {r['eat_share']:6.2f} {r['kills_per_k']:7.3f}")
    if a.out:
        Path(a.out).write_text(json.dumps({"args": vars(a), "result": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
