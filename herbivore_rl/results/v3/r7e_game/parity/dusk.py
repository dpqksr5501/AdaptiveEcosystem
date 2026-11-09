"""parity.py 의 어긋남 진단 — 쫓긴 사건·도망 시작이 언리얼에서 더 많은 때를 10 초 기록 줄 단위로 찾는다 (읽기만, 세계 규칙 그대로).

    # herbivore_rl/ 에서 (PYTHONUTF8=1) — parity.py convert 뒤
    python results/v3/r7e_game/parity/dusk.py --runs <scratch>/r7e_game/runs --work <scratch>/r7e_parity --sessions 20020-20031 --workers 12 \
        --out results/v3/r7e_game/parity/dusk.json

언리얼: 판마다 10 초 기록 줄에서 누적 도망 시작·쫓긴 사건·실행 FLEE(도망 줄 누적), 지역 첫 줄의 늑대 상태(잠·눕는 중·쫓는 중 = 잠행 + 돌진 + 추격)·어둠 d,
  늑대 밤잠(서서히) 구간 칸 합(눕기 시작·다시 일어남·잠듦·깸 — 수, 사슴 곁이라 안 누움·사냥 중이라 안 누움 — 늑대·업데이트).
파이썬: parity.py 와 같은 세계(옮긴 calm 세계·스냅숏 먹이 지도·같은 시드 계획의 반복 0)를 돌려 75 스텝(10 초)마다 같은 누적 칸과 늑대 상태(자는 늑대·표적 있는 늑대)·d,
  끝에 realism_stats 의 밤잠 칸(settle_n 눕기 시작·settle_abort_n·onset_n 잠듦·wake_n·block_deer_n·block_hunt_n — world.py REALISM_STAT_COLUMNS 주석,
  C++ 기록 줄 '늑대 밤잠(서서히)' 과 같은 이름의 셈).
출력: 10 초 칸마다 두 쪽 세션당 값(지역 셋 합)과 지역마다 값.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import parity as pa  # noqa: E402

R_MAIN = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) \| ([\d.]+)초 \S+ d=([\d.]+) .*?\| 늑대 \d+: 배회 (\d+) 잠행 (\d+) 돌진 (\d+) 지침 (\d+) 추격 (\d+) "
                    r"식사 (\d+) 잠 (\d+) 눕는 중 (\d+)")
R_NIGHT = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) \| ([\d.]+)초 .*?늑대 밤잠\(서서히\): 눕기 시작 (\d+) · 다시 일어남 (\d+) · 잠듦 (\d+) · 깸 (\d+) · "
                     r"사슴 곁이라 안 누움 (\d+) · 사냥 중이라 안 누움 (\d+)")
R_FL = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 도망 \| ([\d.]+)초 \|.*?누적 시작 (\d+) · .*?반사 스텝 \d+/(\d+) · .*?쫓긴 사건 (\d+) 중")
TICKS = [round(10.0 * k, 1) for k in range(1, 31)]


def unreal(runs: Path, name: str) -> dict:
    out = {r: {} for r in pa.REGIONS}
    night = {r: dict(settle_n=0, settle_abort_n=0, onset_n=0, block_deer_n=0, block_hunt_n=0, wake_n=0) for r in pa.REGIONS}
    for s in (runs / f"{name}.ecov3.log").read_text(encoding="utf-8", errors="replace").splitlines():
        m = R_NIGHT.search(s)
        if m:
            nr = night[m.group(1)]
            nr["settle_n"] += int(m.group(3))         # 눕기 시작 (파이썬 settle_n)
            nr["settle_abort_n"] += int(m.group(4))   # 다시 일어남
            nr["onset_n"] += int(m.group(5))          # 잠듦 (파이썬 onset_n)
            nr["wake_n"] += int(m.group(6))
            nr["block_deer_n"] += int(m.group(7))
            nr["block_hunt_n"] += int(m.group(8))
        m = R_MAIN.search(s)
        if m:
            t = float(m.group(2))
            out[m.group(1)].setdefault(t, {}).update(d=float(m.group(3)), roam=int(m.group(4)), chase=int(m.group(5)) + int(m.group(6)) + int(m.group(8)),
                                                     eat=int(m.group(9)), asleep=int(m.group(10)), lying=int(m.group(11)))
            continue
        m = R_FL.search(s)
        if m:
            out[m.group(1)].setdefault(float(m.group(2)), {}).update(started=int(m.group(3)), flee=int(m.group(4)), chased=int(m.group(5)))
    out["_night"] = night
    return out


def py_one(job: dict) -> dict:
    import env.torch_init  # noqa: F401
    import numpy as np
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import World

    import adapt

    w = World(Config(job["cfg"]), seeds=[int(job["seed"])])
    adapt.apply_snapshot_food(w, job["cap"])
    w.track_flight = True
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, int(job["seed"]))
    ro.forward_bind(pol, w)
    out = {}
    for _ in range(int(job["steps"])):
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        if w.t % 75 == 0:
            f = w.flight_stats()
            asleep = int(np.count_nonzero(w.pred_asleep)) if getattr(w, "_ps", None) is not None else 0
            out[round(w.t * pa.STEP_S, 1)] = dict(d=float(w.dark), asleep=asleep, chase=int(np.count_nonzero(np.asarray(w.pred_target) >= 0)),
                                                hunting=int(np.count_nonzero(w._wf_hunting())), started=int(f["started"]), flee=int(f["flee_steps"]),
                                                chased=int(f["episode"]["chased"]))
    rz = w.realism_stats()
    night = {k: float(rz[k]) for k in ("settle_n", "settle_abort_n", "onset_n", "block_deer_n", "block_hunt_n", "wake_n", "dark_awake_frac")}
    return dict(session=job["session"], region=job["region"], brain=job["brain"], series=out, night=night)


def main(argv=None) -> int:
    from concurrent.futures import ProcessPoolExecutor

    from env_v2 import rollout as ro

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--sessions", default="20020-20031")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    runs, work = Path(a.runs), Path(a.work)
    sessions = pa.parse_sessions(a.sessions)
    t0 = time.time()
    jobs = [j for j in pa.make_jobs(work, sessions, 1, "calm", list(pa.BRAINS))]
    for j in jobs:
        j.pop("name")
    with ProcessPoolExecutor(max_workers=a.workers, initializer=ro._init_worker) as ex:
        res = list(ex.map(py_one, jobs))
    U = {b: {s: unreal(runs, f"it_s{s}_{b}") for s in sessions} for b in pa.BRAINS}
    keys = ("started", "chased", "flee", "asleep", "chase", "d")
    table = {}
    for b in pa.BRAINS:
        for side in ("unreal", "python"):
            for reg in pa.REGIONS + ("all",):
                rows = {}
                for t in TICKS:
                    acc = {k: 0.0 for k in keys}
                    regs = pa.REGIONS if reg == "all" else (reg,)
                    for s in sessions:
                        for r in regs:
                            if side == "unreal":
                                v = U[b][s][r].get(t, {})
                            else:
                                v = next(x for x in res if x["session"] == s and x["region"] == r and x["brain"] == b)["series"].get(t, {})
                            for k in keys:
                                acc[k] += float(v.get(k, float("nan"))) / len(sessions) / (len(regs) if k == "d" else 1)
                    rows[str(t)] = acc
                table[f"{b}|{side}|{reg}"] = rows
    night = {}
    for b in pa.BRAINS:
        for reg in pa.REGIONS + ("all",):
            regs = pa.REGIONS if reg == "all" else (reg,)
            nk = ("settle_n", "settle_abort_n", "onset_n", "block_deer_n", "block_hunt_n", "wake_n")
            night[f"{b}|unreal|{reg}"] = {k: sum(U[b][s]["_night"][r][k] for s in sessions for r in regs) / len(sessions) for k in nk}
            night[f"{b}|python|{reg}"] = {k: sum(x["night"][k] for x in res if x["brain"] == b and x["region"] in regs) / len(sessions) for k in nk}
    out = dict(sessions=sessions, seeds="parity.py 시드 계획 반복 0", ticks=TICKS, table=table, night=night, wall_s=round(time.time() - t0, 1),
               note="세션당 (지역 셋 합은 all). started·chased·flee 는 누적, asleep·chase 는 그 시각 늑대 수, d 는 지역 평균 어둠")
    Path(a.out).write_text(json.dumps(pa._clean(out), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    for b in pa.BRAINS:
        print(f"== {b} 모든 지역 (세션당): 초 | 언리얼 도망 시작·쫓긴 사건 누적·자는 늑대·쫓는 늑대·d | 파이썬 같은 칸")
        for t in TICKS:
            u, p = table[f"{b}|unreal|all"][str(t)], table[f"{b}|python|all"][str(t)]
            print(f"{t:6.1f} | {u['started']:7.1f} {u['chased']:6.1f} {u['asleep']:5.2f} {u['chase']:5.2f} {u['d']:4.2f} | "
                  f"{p['started']:7.1f} {p['chased']:6.1f} {p['asleep']:5.2f} {p['chase']:5.2f} {p['d']:4.2f}")
    print("== 밤잠 (세션당 누적: 눕기 시작·다시 일어남·잠듦·사슴 곁이라 안 누움·사냥 중이라 안 누움(늑대·업데이트)·깸)")
    for b in pa.BRAINS:
        for reg in pa.REGIONS + ("all",):
            u, p = night[f"{b}|unreal|{reg}"], night[f"{b}|python|{reg}"]
            print(f"{b:4s} {reg:9s} U " + " ".join(f"{u[k]:7.1f}" for k in u) + " | P " + " ".join(f"{p[k]:7.1f}" for k in p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
