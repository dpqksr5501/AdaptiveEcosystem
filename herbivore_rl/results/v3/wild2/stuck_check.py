"""야생 2단계 3 세로 장애물 — 늑대·사슴 끼임 세기 (10-17 장애물 돌아가기 검증 도구, 측정 전용 — 동역학을 건드리지 않는다).

    # herbivore_rl/ 에서
    python results/v3/wild2/stuck_check.py --seeds 32000-32029 --steps 7200                      # 지금 장애물 거울(configs/v3_wild2_obstacle_mirror.yaml)
    python results/v3/wild2/stuck_check.py --seeds 32000-32029 --steps 7200 --set obstacles.detour=false   # 돌아가기를 끈 판
    python results/v3/wild2/stuck_check.py --config configs/v3_wild2_pack_mirror.yaml --seeds 32000-32029   # 장애물 없는 판(기준)
    python results/v3/wild2/stuck_check.py --seeds 32000-32089 --steps 1800 --unreal-maps 20000-20002 --replicates 10 \
        --unreal-obstacles results/v3/wild2/shc/obstacle_maps                                      # 언리얼 짝 지도·원판 (10-17 SHC 거울)
    python results/v3/wild2/stuck_check.py --config configs/v3_wild3_mirror.yaml --seeds 32000-32089 --steps 1800 --unreal-maps 20000-20002 --replicates 10 \
        --unreal-obstacles results/v3/wild2/trees/tree_layout.json                                 # 10-18 날씨 거울: 지도 지역마다 나무·날씨(run_mirror 와 같다)

세계는 거울 실행기(results/v3/mirror/run_mirror.py)와 같다: 사슴 128, 늑대 식사 5초(38스텝), 두뇌 R1b 배포 모드. 시드마다 세계 하나를 돌리며 스텝마다
이동 뒤 위치를 읽는다. '가려던 이동'은 세계가 원판 미끄러짐(world.py `obstacle_slide`)에 넘기는 이동 길이다 — 그 함수를 감싸 사슴 이동(World.step 이
부름)과 늑대 이동(World._step_predators_v3 가 부름)의 |가려던 자리 − 이동 전| 을 적는다(돌아가기 `detour_moves` 의 시험 호출은 빼고, 세계 규칙은 그대로).
원판이 없는 세계의 늑대는 은신처 밀어내기(World._rz_wall_push)가 받는 |이동 뒤 − 이동 전| 을 가려던 이동으로 쓴다(사슴은 모른다 — 사슴 세기 0).

세는 것 (1 단위 = 2 m, 1 스텝 = 8/60 초):
  끼임(이 도구의 기준, 10-17 목표 '3 초 넘게 끼인 늑대·사슴 0'): 개체마다 3 초 창(WIN = 23 스텝)이 끝나는 스텝 t 에서
      창 안 모든 스텝에 가려던 이동 > 1e-9 (움직이려 했다) ∧ 창 안에 원판 부딪힘(그 스텝 미끄러짐이 원판에 닿음 — obstacle_slide 의 hit)이 한 번이라도 있음
      ∧ |위치(t) − 위치(t − WIN)| < STILL = 0.5 (1 m) ∧ 창 안 실제로 간 길(스텝마다 |위치 차| 의 합) < PATH_FRAC = 0.5 × 가려던 이동 길이의 합
      ∧ (사슴) 창 내내 살아 있음
    마지막 조건은 막힘과 서성임을 가른다 — 먹으며 걷는 사슴은 자주 가던 길을 되돌아 3 초 순 이동이 1 m 안일 수 있지만 그때는 가려던 만큼 실제로 간다.
    늑대는 막힘을 둘로 나눠 센다: 원판 부딪힘(위) 과 은신처 막기 둘레 닿음(|q − c| − (r + 몸 여유) < TOUCH = 0.05 — 늑대가 들어가지 못하는 덤불 가장자리).
    '원판' 끼임 = 원판 부딪힘이 있는 창, '은신처 둘레' 끼임 = 원판 부딪힘 없이 은신처 둘레 닿음만 있는 창(원판이 없는 세계에도 있다 — 10-16 늑대 진입
    금지의 몫. 둘레 곁에 줄기가 있어도 부딪히지 않았으면 이쪽이다).
    끼임 기록에는 첫 끼인 창 안에서 은신처 둘레에도 닿았나(wall)·돕는 늑대였나(helper)를 적는다.
    이면 '끼인 창'이다. 끼인 창이 이어진 구간 하나 = 끼임 한 번, 길이 = 이어진 창 수 + WIN − 1 스텝(3 초 넘음). 사슴은 끼임 첫 창의 첫 스텝 행동
    (먹기·도망·숨기)과 도주 반사(wf_mode 도주) 여부, 늑대는 그때 돕는 늑대였나를 적는다.
    끼인 몫 = 끼인 창 수 ÷ 움직이려 한 창 수(창 안 모든 스텝에 가려던 이동 > 1e-9).
  검증 기록과 같은 세기(81c6409 검증): 늑대 돌아섬·되돌림(pred_ob_dead ∨ pred_ob_back)이 23 스텝 넘게 이어진 수, 사슴이 원판에 닿은 채(위 TOUCH)
    38 스텝(5 초) 넘게 이어지고 그동안 순 이동 < 0.5 인 수 — 그중 도주 스텝 > 10(뛰는 자세로 낀 사슴)·지나온 길 > 2 단위(제자리걸음)인 수.
출력: 표 한 묶음(stdout)과 --out JSON(세계마다 세기·끼임 목록).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (ROOT, ROOT / "results" / "v3" / "mirror"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

OBST = ROOT / "configs" / "v3_wild2_obstacle_mirror.yaml"
WIN = 23            # 3 초 (23 × 8/60 = 3.07 초)
STILL = 0.5         # 1 m
PATH_FRAC = 0.5     # 창 안 실제 길 ÷ 가려던 길이 이것보다 작으면 막힘
TOUCH = 0.05        # 둘레까지 10 cm 안이면 닿음
OLD_WOLF = 23       # 검증 기록: 늑대 돌아섬·되돌림 3 초 넘게
OLD_DEER = 38       # 검증 기록: 사슴 닿음 5 초 넘게


def parse_set(items) -> list[tuple[str, str, object]]:
    """--set 블록.키=값 (값은 JSON — true·false·수·목록, 아니면 문자열)."""
    out = []
    for it in items or ():
        k, _, v = it.partition("=")
        blk, _, key = k.partition(".")
        if not blk or not key or not _:
            raise ValueError(f"--set 은 블록.키=값 이어야 한다: {it!r}")
        try:
            val = json.loads(v)
        except json.JSONDecodeError:
            val = v
        out.append((blk, key, val))
    return out


def build_cfg(config: Path, sets) -> dict:
    import run_mirror as rm
    cfg = rm.mirror_cfg(128, rm.eat_steps_of_seconds(5.0), config)
    if sets:
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        for blk, key, val in sets:
            if blk not in f:
                raise ValueError(f"설정에 기능 블록 {blk} 가 없다")
            f[blk][key] = val
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    return cfg.to_dict()


class _Runs:
    """끼인 창이 이어진 구간 (개체마다)."""

    def __init__(self, n: int):
        self.run = np.zeros(n, dtype=np.int64)
        self.t0 = np.zeros(n, dtype=np.int64)
        self.tag = [None] * n
        self.events: list[dict] = []

    def update(self, t: int, stuck: np.ndarray, tag_of) -> None:
        start = stuck & (self.run == 0)
        for i in np.flatnonzero(start):
            self.t0[i] = t - WIN + 1
            self.tag[i] = tag_of(int(i))
        end = ~stuck & (self.run > 0)
        for i in np.flatnonzero(end):
            self._close(int(i))
        self.run = np.where(stuck, self.run + 1, 0)

    def _close(self, i: int) -> None:
        self.events.append(dict(id=i, t0=int(self.t0[i]), steps=int(self.run[i]) + WIN - 1, **(self.tag[i] or {})))

    def finish(self) -> None:
        for i in np.flatnonzero(self.run > 0):
            self._close(int(i))
        self.run[:] = 0


def one(job: dict) -> dict:
    from env.config import Config
    from env_v2 import repertoire as rep
    from env_v2 import rollout as ro
    from env_v2 import world as wm
    import run_mirror as rm

    want = {"deer": None, "wolf": None, "wall": None, "deer_hit": None, "wolf_hit": None}
    orig = wm.obstacle_slide
    orig_push = wm.World._rz_wall_push

    def rec_push(self, q, p, sel):
        want["wall"] = np.sqrt(((np.asarray(q, dtype=np.float64) - np.asarray(p, dtype=np.float64)) ** 2).sum(1))
        return orig_push(self, q, p, sel)

    def rec_slide(p, q, discs, body_r, size=None):
        caller = sys._getframe(1).f_code.co_name     # 세계의 실제 이동 두 곳만 적는다(돌아가기 시험 호출 detour_moves 는 빼고)
        out = orig(p, q, discs, body_r, size)
        if caller in ("step", "_step_predators_v3"):
            d = np.sqrt(((np.asarray(q, dtype=np.float64) - np.asarray(p, dtype=np.float64)) ** 2).sum(1))
            k = "deer" if caller == "step" else "wolf"
            want[k] = d
            want[k + "_hit"] = np.asarray(out[1], dtype=bool)
        return out

    wm.obstacle_slide = rec_slide
    wm.World._rz_wall_push = rec_push
    try:
        w = wm.World(Config(job["cfg"]), seeds=[int(job["seed"])])
        um = job.get("unreal_map")
        if um is not None:
            rm.apply_unreal_map(w, int(um["seed"]), um["region"])      # 짝 비교: 언리얼 지역 무대와 같은 먹이 지도(run_mirror.run_world 와 같은 순서)
        pol = ro.build_policy({"kind": "rep_learned", "path": str(rm.MODEL)}, int(job["seed"]))
        ro.forward_bind(pol, w)
        T, M, N = int(job["steps"]), w.M, w.N
        ob = getattr(w, "_ob", None) is not None and len(w.obstacles) > 0
        disc = w.obstacles if ob else np.zeros((0, 3))
        body = float(w._ob["body_r"]) if ob else 0.0
        H = WIN + 1
        wpos = np.zeros((H, M, 2)); wpos[0] = w.pred_pos
        dpos = np.zeros((H, N, 2)); dpos[0] = w.pos
        wwant = np.zeros((H, M), dtype=bool)
        dwant = np.zeros((H, N), dtype=bool)
        wlen = np.zeros((H, M)); wgo = np.zeros((H, M))      # 스텝마다 가려던 이동 길이·실제 이동 길이
        dlen = np.zeros((H, N)); dgo = np.zeros((H, N))
        wtouch = np.zeros((H, M), dtype=bool)
        wwall = np.zeros((H, M), dtype=bool)
        whelp = np.zeros((H, M), dtype=bool)
        dtouch = np.zeros((H, N), dtype=bool)
        dalive = np.ones((H, N), dtype=bool)
        wr, dr, wl = _Runs(M), _Runs(N), _Runs(M)
        win_w = win_d = st_w = st_d = st_wl = 0
        wall_r = (w.cov_r + w._zw_m) if getattr(w, "_zw", False) and len(w.cov_r) else None

        def wall_of(q):
            if wall_r is None:
                return np.zeros(len(q), dtype=bool)
            dd = np.sqrt(((q[:, None, :] - w.cov_c[None, :, :]) ** 2).sum(-1)) - wall_r[None, :]
            return np.abs(dd).min(1) < TOUCH
        # 검증 기록 세기
        wdead_run = np.zeros(M, dtype=np.int64); old_w = []
        drun = np.zeros(N, dtype=np.int64); dp0 = w.pos.copy(); dpath = np.zeros(N); dflee = np.zeros(N, dtype=np.int64)
        dprev = w.pos.copy(); old_d = []

        def touch_of(q):
            if not ob:
                return np.zeros(len(q), dtype=bool)
            dd = np.sqrt(((q[:, None, :] - disc[None, :, :2]) ** 2).sum(-1)) - disc[None, :, 2]
            return dd.min(1) - body < TOUCH

        for t in range(1, T + 1):
            want["deer"] = want["wolf"] = want["wall"] = want["deer_hit"] = want["wolf_hit"] = None
            alive0 = w.alive.copy() if w.alive is not None else np.ones(N, dtype=bool)
            beh0 = w._rs.behavior.copy()
            wf0 = w.wf_mode.copy() if getattr(w, "wf_mode", None) is not None else None
            help0 = w.pack_help.copy() if getattr(w, "pack_help", None) is not None else np.zeros(M, dtype=bool)
            w.step(np.asarray(pol(w.observe()), dtype=np.float64))
            h = t % H
            hp = (t - 1) % H
            wpos[h], dpos[h] = w.pred_pos, w.pos
            wsrc = want["wolf"] if want["wolf"] is not None else want["wall"]
            wwant[h] = wsrc > 1e-9 if wsrc is not None else False
            wlen[h] = wsrc if wsrc is not None else 0.0
            dlen[h] = np.where(alive0, want["deer"], 0.0) if want["deer"] is not None else 0.0
            wgo[h] = np.linalg.norm(wpos[h] - wpos[hp], axis=1)
            dgo[h] = np.linalg.norm(dpos[h] - dpos[hp], axis=1)
            dwant[h] = (want["deer"] > 1e-9) & alive0 if want["deer"] is not None else False
            wtouch[h] = want["wolf_hit"] if want["wolf_hit"] is not None else False
            dtouch[h] = (want["deer_hit"] & alive0) if want["deer_hit"] is not None else False
            dnear = touch_of(w.pos) & alive0          # 검증 기록 세기(아래)는 닿음 거리로 센다
            wwall[h] = wall_of(w.pred_pos)
            if getattr(w, "pack_help", None) is not None:
                whelp[h] = w.pack_help
            dalive[h] = alive0
            if t >= WIN:
                h0 = (t - WIN) % H
                idx = [(t - k) % H for k in range(WIN)]
                ww = wwant[idx].all(0)
                dw = dwant[idx].all(0) & dalive[idx].all(0)
                w_still = (ww & (np.linalg.norm(wpos[h] - wpos[h0], axis=1) < STILL) & (wgo[idx].sum(0) < PATH_FRAC * wlen[idx].sum(0)))
                s_w = w_still & wtouch[idx].any(0)
                s_wl = w_still & ~wtouch[idx].any(0) & wwall[idx].any(0)
                st_wl += int(s_wl.sum())
                wl.update(t, s_wl, lambda m: dict(helper=bool(whelp[idx, m].any()), wall=True))
                s_d = (dw & dtouch[idx].any(0) & (np.linalg.norm(dpos[h] - dpos[h0], axis=1) < STILL)
                       & (dgo[idx].sum(0) < PATH_FRAC * dlen[idx].sum(0)))
                win_w += int(ww.sum()); win_d += int(dw.sum()); st_w += int(s_w.sum()); st_d += int(s_d.sum())
                wr.update(t, s_w, lambda m: dict(helper=bool(whelp[idx, m].any()), wall=bool(wwall[idx, m].any())))
                dr.update(t, s_d, lambda i: dict(beh=int(beh0[i]), panic=bool(wf0 is not None and wf0[i] == wm.WF_PANIC)))
            if ob:
                dw_ = w.pred_ob_dead | w.pred_ob_back
                for m in np.flatnonzero(~dw_ & (wdead_run > OLD_WOLF)):
                    old_w.append(dict(id=int(m), steps=int(wdead_run[m]), t_end=t))
                wdead_run = np.where(dw_, wdead_run + 1, 0)
                tch = dnear
                step_len = np.linalg.norm(w.pos - dprev, axis=1); dprev = w.pos.copy()
                for i in np.flatnonzero(tch & (drun == 0)):
                    dp0[i] = w.pos[i]; dpath[i] = 0.0; dflee[i] = 0
                dpath = dpath + np.where(tch, step_len, 0.0)
                dflee = dflee + (tch & (beh0 == rep.FLEE)).astype(np.int64)
                for i in np.flatnonzero(~tch & (drun > OLD_DEER)):
                    old_d.append(dict(id=int(i), steps=int(drun[i]), net=float(np.linalg.norm(w.pos[i] - dp0[i])), path=float(dpath[i]),
                                      flee=int(dflee[i]), t_end=t))
                drun = np.where(tch, drun + 1, 0)
        wr.finish(); dr.finish(); wl.finish()
        for m in np.flatnonzero(wdead_run > OLD_WOLF):
            old_w.append(dict(id=int(m), steps=int(wdead_run[m]), t_end=T))
        for i in np.flatnonzero(drun > OLD_DEER):
            old_d.append(dict(id=int(i), steps=int(drun[i]), net=float(np.linalg.norm(w.pos[i] - dp0[i])), path=float(dpath[i]),
                              flee=int(dflee[i]), t_end=T))
        det = w.obstacle_stats().get("detour", None) if ob and hasattr(w, "obstacle_stats") else None
    finally:
        wm.obstacle_slide = orig
        wm.World._rz_wall_push = orig_push
    return dict(seed=int(job["seed"]), unreal_map=job.get("unreal_map"), discs=int(len(disc)), wolf_events=wr.events, deer_events=dr.events, wall_events=wl.events, win_w=win_w,
                win_d=win_d, stuck_w=st_w, stuck_d=st_d, stuck_wall=st_wl, old_wolf=old_w, old_deer=old_d, detour=det)


def summarize(res: list[dict]) -> dict:
    we = [dict(e, seed=r["seed"]) for r in res for e in r["wolf_events"]]
    de = [dict(e, seed=r["seed"]) for r in res for e in r["deer_events"]]
    ow = [dict(e, seed=r["seed"]) for r in res for e in r["old_wolf"]]
    od = [dict(e, seed=r["seed"]) for r in res for e in r["old_deer"]]
    od_still = [e for e in od if e["net"] < STILL]
    names = {0: "graze", 1: "flee", 2: "hide", 3: "freeze", 4: "sleep"}
    wle = [dict(e, seed=r["seed"]) for r in res for e in r["wall_events"]]
    s = dict(worlds=len(res),
             wolf_stuck=len(we), wolf_stuck_helper=sum(e["helper"] for e in we), wolf_stuck_wall=sum(e["wall"] for e in we),
             wolf_stuck_max_s=max([e["steps"] for e in we], default=0) * 8 / 60,
             wolf_wall_stuck=len(wle), wolf_wall_stuck_helper=sum(e["helper"] for e in wle),
             wolf_wall_stuck_max_s=max([e["steps"] for e in wle], default=0) * 8 / 60,
             deer_stuck=len(de), deer_stuck_by_beh={names[b]: sum(1 for e in de if e["beh"] == b) for b in sorted({e["beh"] for e in de})},
             deer_stuck_panic=sum(e["panic"] for e in de), deer_stuck_max_s=max([e["steps"] for e in de], default=0) * 8 / 60,
             wolf_stuck_frac=sum(r["stuck_w"] for r in res) / max(sum(r["win_w"] for r in res), 1),
             wolf_wall_stuck_frac=sum(r["stuck_wall"] for r in res) / max(sum(r["win_w"] for r in res), 1),
             deer_stuck_frac=sum(r["stuck_d"] for r in res) / max(sum(r["win_d"] for r in res), 1),
             old_wolf_runs=len(ow), old_wolf_max_s=max([e["steps"] for e in ow], default=0) * 8 / 60,
             old_deer_still=len(od_still), old_deer_flee=sum(1 for e in od_still if e["flee"] > 10),
             old_deer_push=sum(1 for e in od_still if e["path"] > 2.0), old_deer_max_s=max([e["steps"] for e in od_still], default=0) * 8 / 60)
    s["worst_wolf"] = sorted(((e["steps"], e["seed"], e["id"], e["t0"], e["helper"], e["wall"]) for e in we), reverse=True)[:6]
    s["worst_wolf_wall"] = sorted(((e["steps"], e["seed"], e["id"], e["t0"], e["helper"]) for e in wle), reverse=True)[:6]
    s["worst_deer"] = sorted(((e["steps"], e["seed"], e["id"], e["t0"], names[e["beh"]], e["panic"]) for e in de), reverse=True)[:6]
    dets = [r["detour"] for r in res if r.get("detour")]
    if dets:
        s["detour"] = {k: sum(d[k] for d in dets) for k in dets[0]}
    return s


def main(argv=None) -> None:
    import run_mirror as rm
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=OBST)
    ap.add_argument("--seeds", default="32000-32029")
    ap.add_argument("--steps", type=int, default=7200, help="스텝 (7200 = 16 분, 1800 = 240 초)")
    ap.add_argument("--set", action="append", default=[], help="설정 덮기 블록.키=값 (예: obstacles.detour=false)")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--unreal-maps", default=None, help="짝 비교(run_mirror.py 와 같다): 언리얼 세션 시드(예: 20000-20002)의 지역 먹이 지도를 쓴다")
    ap.add_argument("--replicates", type=int, default=1, help="짝 비교: 지도마다 세계 수 (지도 i 의 j 번째 = seeds[i·replicates + j])")
    ap.add_argument("--unreal-obstacles", type=Path, default=None, help="짝 비교: 장애물 JSON(파일 또는 s<세션>.json 폴더)의 지역 원판을 fixed 로")
    a = ap.parse_args(argv)
    cfg = build_cfg(a.config if a.config.is_absolute() else ROOT / a.config, parse_set(a.set))
    seeds = rm.parse_seeds(a.seeds)
    jobs = [dict(cfg=cfg, seed=s, steps=a.steps) for s in seeds]
    if a.unreal_maps:
        # 10-17 더함(팀 SHC 레벨 거울, results/v3/wild2/shc/README.md): run_mirror.run 과 같은 짝 — 지도 (세션, 지역 Barren·Forest·Highland) 마다
        # replicates 개 세계, 원판은 그 지도의 fixed(난수 없음)
        import copy
        um = rm.parse_unreal_maps(a.unreal_maps)
        maps = [(int(u), r) for u in um for r in sorted(rm.UNREAL_REGION_STREAM)]
        k = int(a.replicates)
        if k < 1 or len(seeds) != len(maps) * k:
            raise ValueError(f"짝 비교는 시드가 지도 {len(maps)}장 × replicates {k} = {len(maps) * k}개여야 한다. 받은 수 {len(seeds)}")
        obs = rm.load_unreal_obstacles(a.unreal_obstacles, um) if a.unreal_obstacles is not None else None
        wx_on = bool(cfg["v2"]["features"].get("wild_weather", {}).get("enabled"))
        for i, (u, r) in enumerate(maps):
            for j in range(k):
                jb = jobs[i * k + j]
                jb["unreal_map"] = dict(seed=u, region=r, replicate=j)
                if obs is not None or wx_on:
                    c = copy.deepcopy(jb["cfg"])
                    if obs is not None:
                        c["v2"]["features"]["obstacles"]["fixed"] = obs[(u, r)]
                    if wx_on:
                        # 10-18 야생 3단계: 그 지도 지역의 날씨(run_mirror.run 과 같다)
                        c["v2"]["features"]["wild_weather"]["region"] = r
                    jb["cfg"] = c
    elif a.unreal_obstacles is not None:
        raise ValueError("--unreal-obstacles 는 --unreal-maps 와 함께 쓴다")
    if a.workers > 0:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(one, jobs))
    else:
        res = [one(j) for j in jobs]
    s = summarize(res)
    if a.unreal_maps:
        regs = sorted({r["unreal_map"]["region"] for r in res})
        s["by_region"] = {g: {k: v for k, v in summarize([r for r in res if r["unreal_map"]["region"] == g]).items() if not k.startswith("worst")}
                          for g in regs}
    print(f"{a.config.name} {a.seeds} {a.steps} 스텝 {' '.join(a.set)}"
          + (f" | 짝 지도 {a.unreal_maps} × {a.replicates}{' · 원판 ' + str(a.unreal_obstacles) if a.unreal_obstacles else ''}" if a.unreal_maps else ""))
    for k, v in s.items():
        print(f"  {k}: {v}")
    if a.out is not None:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(dict(args=dict(config=str(a.config), seeds=a.seeds, steps=a.steps, set=a.set, unreal_maps=a.unreal_maps,
                                                   replicates=a.replicates,
                                                   unreal_obstacles=None if a.unreal_obstacles is None else str(a.unreal_obstacles)),
                                         summary=s, worlds=res),
                                    ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
