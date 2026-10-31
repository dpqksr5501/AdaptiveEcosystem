"""a1_summary_<seeds>.json → 터미널 표 (보고서 파일은 쓰지 않는다)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
seeds = sys.argv[1] if len(sys.argv) > 1 else "eval"
what = sys.argv[2] if len(sys.argv) > 2 else "all"
S = json.load(open(HERE.parent / f"a1_summary_{seeds}.json", encoding="utf-8"))
per, groups, models = S["per_model"], S["groups"], S["models"]
order = [m for m, g in models.items() if g == "good"] + [m for m, g in models.items() if g == "bad"] + \
        [m for m, g in models.items() if g == "border"]
short = {m: m.replace("v2_2r_t0_", "T0_").replace("v2_1c_", "c").replace("v2_1_", "v21_") for m in models}


def f(x, d=3):
    return "nan" if x is None or x != x else f"{x:.{d}f}"


def whole(md):
    cols = ("g_gamma", "starve_rate", "predation_rate", "hungry_frac", "stop_frac_cmd", "run_frac_cmd",
            "p_stop_hungry", "p_stop_full", "mean_forage", "mean_cohesion", "mean_cover", "mean_cos_grad",
            "mean_in_cover", "intake_per_step", "drain_per_step")
    print(f"\n## whole {md}")
    print("model grp " + " ".join(c[:9] for c in cols))
    for m in order:
        s = per[m].get(md)
        if not s:
            continue
        w = s["whole"]
        print(f"{short[m]:8s} {models[m][:4]} " + " ".join(f(w[c], 5 if 'rate' in c or 'step' in c else 3) for c in cols))


def gcmp(md, prefix_filter, cols=None):
    g = groups[md]
    for k, v in g.items():
        if not k.startswith(prefix_filter):
            continue
        if cols and k.split(".")[-1] not in cols:
            continue
        print(f"{k:45s} good {f(v['good'], 4)} [{f(v['good_min'], 4)},{f(v['good_max'], 4)}] bad {f(v['bad'], 4)} "
              f"diff {f(v['diff'], 4)} t {f(v['t'], 2)} badvals {' '.join(f(x, 4) for x in v['bad_vals'])}")


def bins(md, cols=("occ", "cmd_stop", "cmd_run", "forage", "cohesion", "cover", "net", "intake", "drain", "cell_food",
                   "cos_grad")):
    print(f"\n## bins {md}: per model")
    for src in ("merged", "bins"):
        labels = list(per[order[0]][md][src])
        for bl in labels:
            print(f"-- {bl}")
            print("model    " + " ".join(f"{c[:8]:>8s}" for c in cols))
            for m in order:
                s = per[m].get(md)
                if not s:
                    continue
                x = s[src][bl]
                print(f"{short[m]:8s} " + " ".join(f"{f(x[c], 4):>8s}" for c in cols))


def deaths(md):
    print(f"\n## starvation deaths {md}")
    cols = ("n", "share_stop", "share_walk_nofood", "share_walk_food", "stop_on_emptycell", "age_median", "never_fed",
            "last_food_density", "last_cell_food", "last_forage", "last_cmd_stop", "last_cover", "last_intake",
            "life_food_density", "life_cmd_stop", "life_forage")
    print("model    " + " ".join(f"{c[-9:]:>9s}" for c in cols))
    for m in order:
        s = per[m].get(md)
        if not s:
            continue
        x = s["death"]
        print(f"{short[m]:8s} " + " ".join(f"{f(x.get(c), 4):>9s}" for c in cols))
    print(f"\n## crisis {md}")
    for m in order:
        s = per[m].get(md)
        if not s:
            continue
        c = s["crisis"]
        print(f"{short[m]:8s} " + " ".join(f"{k} {f(v, 4)}" for k, v in c.items()))


def traj(md):
    print(f"\n## traj before starvation {md}")
    cols = ("energy", "food_density", "cell_food", "cmd_stop", "cmd_run", "forage", "cover", "intake", "drain", "cos_grad")
    for m in order:
        s = per[m].get(md)
        if not s:
            continue
        for wl, x in s["traj"].items():
            print(f"{short[m]:8s} {wl:8s} n={x['n']:.0f} " + " ".join(f"{c[:6]}={f(x[c], 4)}" for c in cols))


def fine(md, grp="all"):
    print(f"\n## fine {md} {grp}: energy decile curves (unseen)")
    for key in ("p_stop", "forage", "net"):
        print(f"-- {key}")
        for m in order:
            s = per[m].get(md)
            if not s:
                continue
            print(f"{short[m]:8s} " + " ".join(f(x, 3) for x in s["fine"][grp][key]))


if what in ("all", "whole"):
    for md in per[order[0]]:
        whole(md)
if what in ("all", "bins"):
    for md in per[order[0]]:
        bins(md)
if what in ("all", "deaths"):
    for md in per[order[0]]:
        deaths(md)
if what in ("all", "traj"):
    for md in per[order[0]]:
        traj(md)
if what in ("all", "fine"):
    for md in per[order[0]]:
        for grp in ("all", "f<0.05", "f>=0.05"):
            fine(md, grp)
if what.startswith("g:"):
    _, md, pref = what.split(":", 2)
    gcmp(md, pref)
