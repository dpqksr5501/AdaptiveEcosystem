"""두 길 두뇌 C++ 평가기 판 단위 대조 (이식 계획서 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-2 — 10-24 C++ 이식 검증).

make_traces.py 가 만든 판 24 (두뇌 route0·늘 SHELTER × 세계 N·G × 지역 셋 × 시드 34900·34901 × 1800 스텝)의 일을 같은 길(스냅숏 → live.prepare →
ceval.eval_items + 세계 덮기 features.wild_flight.route = true)로 다시 만들어 네이티브 평가기(AdaptiveEcosystem/Tools/EcoV3Eval — 엔진 무관 EcoWorldV3.h 의
Step 그대로)로 돌리고, 평가기가 스텝마다 낸 궤적 지문(일의 trace_digest — EcoV3Eval.cpp TrajDigest, make_traces.digest_state 와 같은 칸 아홉·같은 바이트)을
traj/<판>.jsonl.gz 와, 세계 기록(ceval.shape 'world' 칸 + flight — flight.route·hide·episode 포함)을 stats/<판>.json 의 record(파이썬 기록)와 견준다.
파이썬을 다시 돌리지 않는다 — 올린 지문·기록이 파이썬 쪽이다(신선도는 tests/test_route_port_v3.py 가 본다).

    # herbivore_rl/ 에서 (Anaconda base python, PYTHONUTF8=1). 평가기 빌드 먼저 (AdaptiveEcosystem/Tools/EcoV3Eval/build.ps1)
    python results/v3/route/port/native_check.py [--workers 4] [--only <판 이름> ...] [--steps 1800] [--out <결과 json>]

받아들일 조건 (계획서 10-2 의 1·2): 판마다 궤적 지문 첫 차이 없음(스텝 0..1800 · 칸 아홉), 세계 기록 정확히 같음. 결과는 판마다 첫 차이 스텝·칸, 기록이 다른 칸,
길 결정·SHELTER 고름·숨음 요약. 하나라도 어긋나면 종료 코드 1.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
PORT = HERE.parent
ROOT = HERE.parents[4]                              # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "live", ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
           ROOT / "results" / "v3" / "wild2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저


def _make_traces():
    spec = importlib.util.spec_from_file_location("_make_traces_native", PORT / "make_traces.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def first_diff(cpp: list, py: list, groups) -> dict | None:
    """궤적 지문 줄 목록 둘 → 처음 다른 스텝·칸 (같으면 None)."""
    n = min(len(cpp), len(py))
    for s in range(n):
        a, b = cpp[s], py[s]
        if a == b:
            continue
        diff = [g for j, g in enumerate(groups) if a[1 + j] != b[1 + j]] if len(a) == len(b) else ["(줄 꼴)"]
        return dict(step=s, groups=diff)
    if len(cpp) != len(py):
        return dict(step=n, groups=["(줄 수)"], cpp_lines=len(cpp), py_lines=len(py))
    return None


def record_diff(py: dict, nat: dict) -> dict:
    """파이썬 기록 ↔ 네이티브 기록 (wall_s·native 빼고). 다른 칸·파이썬에만 있는 칸."""
    import ceval

    diff = [k for k in py if k not in ("wall_s", "native") and k in nat and not ceval._same(py[k], nat[k])]
    only = sorted(ceval._only_left({k: v for k, v in py.items() if k != "wall_s"}, nat))
    sub = {}
    if "flight" in diff:
        sub = {k: (py["flight"][k], nat["flight"].get(k)) for k in py["flight"] if k in nat["flight"] and not ceval._same(py["flight"][k], nat["flight"][k])}
        if "route" in sub:
            pr, nr = py["flight"]["route"], nat["flight"]["route"]
            sub["route"] = {k: (pr[k], nr.get(k)) for k in pr if not ceval._same(pr[k], nr.get(k))}
    return dict(same=not diff and not only, differ=diff, python_only=only, flight=sub)


def main(argv=None) -> int:
    import ceval

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--steps", type=int, default=None, help="스텝 수 (기본 = 올린 판 길이 1800 — 짧게 주면 지문 앞부분만 견주고 기록은 견주지 않는다)")
    ap.add_argument("--only", nargs="*", default=None, help="판 이름 (예: v3_obs24route_shelter2__N__Forest__34900)")
    ap.add_argument("--out", type=Path, default=None, help="결과 JSON (기본: AdaptiveEcosystem/Saved/EcoV3Eval/route_port/native_check.json — git 밖)")
    a = ap.parse_args(argv)
    mt = _make_traces()
    full = a.steps is None or int(a.steps) == mt.STEPS
    steps = mt.STEPS if a.steps is None else int(a.steps)
    names = [mt.run_name(*r) for r in mt.all_runs()]
    if a.only is not None and set(a.only) - set(names):
        raise SystemExit(f"없는 판 이름: {sorted(set(a.only) - set(names))}")
    runs = [r for r in mt.all_runs() if a.only is None or mt.run_name(*r) in a.only]
    t0 = time.perf_counter()
    print(f"일 만들기 (스냅숏 → live.prepare → ceval.eval_items, 세계 덮기 {mt.WORLD_SET}) — 판 {len(runs)}, 스텝 {steps}", flush=True)
    jobs = mt.make_jobs(steps)
    out = dict(format="eco_v3_route_port_native_check", version=1, steps=steps, version_tag=ceval.VERSION_TAG, runs=[])
    bad = 0
    for brain in mt.BRAINS:
        rs = [r for r in runs if r[0] == brain]
        if not rs:
            continue
        bj = mt.brain_json(brain)
        bmv = int(json.loads(bj.read_text(encoding="utf-8"))["mask_version"])
        njobs = []
        for k, (b, wd, region, seed) in enumerate(rs):
            nj = ceval.native_job(jobs[(wd, region, seed)], k, brain_mask_version=bmv)
            nj["trace_digest"] = steps
            njobs.append(nj)
        print(f"평가기: 두뇌 {brain} (마스크 판 {bmv}) · 판 {len(njobs)} · 프로세스 {a.workers}", flush=True)
        rows = ceval.run_native(njobs, bj, int(a.workers))
        for (b, wd, region, seed), row in zip(rs, rows):
            nm = mt.run_name(b, wd, region, seed)
            head, py_lines = mt.read_traj(PORT / "traj" / f"{nm}.jsonl.gz")
            cpp_lines = row.get("traj") or []
            fd = first_diff(cpp_lines, py_lines[:steps + 1], mt.GROUPS)
            nat = ceval.shape("world", jobs[(wd, region, seed)], row, 0.0, bj)
            st = json.loads((PORT / "stats" / f"{nm}.json").read_text(encoding="utf-8"))
            rd = record_diff(st["record"], nat) if full else None
            rt = (nat.get("flight") or {}).get("route") or {}
            hide = (nat.get("flight") or {}).get("episode") or {}
            res = dict(run=nm, first_traj_difference=fd, traj_lines=len(cpp_lines), record=rd,
                       native=dict(caught=nat["caught"], starved=nat["starved"], decisions=rt.get("decisions"), choice=rt.get("choice"),
                                   picked_shelter=(rt.get("picked") or {}).get("shelter"), steps_shelter=(rt.get("steps") or {}).get("shelter"),
                                   invalid_shelter=(rt.get("invalid") or {}).get("shelter"), episode_hidden=hide.get("hidden"),
                                   episode_chased=hide.get("chased"), mask_violations=nat["native"]["mask_violations"],
                                   obs_layout_mismatch=nat["native"]["obs_layout_mismatch"]))
            ok = fd is None and len(cpp_lines) == steps + 1 and (rd is None or rd["same"]) and nat["native"]["mask_violations"] == 0 \
                and nat["native"]["obs_layout_mismatch"] == 0
            bad += 0 if ok else 1
            out["runs"].append(res)
            print(f"  {nm:<46} 지문 {'첫 차이 없음' if fd is None else f'첫 차이 스텝 {fd}'} · 기록 "
                  f"{'(짧게 — 견주지 않음)' if rd is None else ('같음' if rd['same'] else f'다름 {rd}')} · 길 결정 {rt.get('decisions')} SHELTER "
                  f"{(rt.get('picked') or {}).get('shelter')} · 사건 숨음 {hide.get('hidden')}/{hide.get('chased')}", flush=True)
    out["ok"] = bad == 0
    out["bad"] = bad
    out["wall_s"] = round(time.perf_counter() - t0, 1)
    dst = a.out or (ceval.CACHE / "route_port" / "native_check.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n판 {len(out['runs'])} 가운데 어긋남 {bad} ({out['wall_s']} 초) -> {dst}", flush=True)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
