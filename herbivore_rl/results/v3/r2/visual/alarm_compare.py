"""동족 경보 물결 — 같은 순간에서 갈라 '경보 무시' 대 '경보 들으면 고개 들기' 두 칸 비교 영상.

원본: 5주차_자료/_build/scenes_plain.py (그 파일은 고치지 않는다. 이 파일은 그 사본을 경보 장면용으로 늘린 것이다).
같은 점: 쉬운 한국어 표기, 맑은 고딕, 행동 색(먹기 초록 / 도망 주황 / 숨기 파랑 / 얼어붙기 흰색 + '!'), 포식자 X 표, 은신처 원,
작은 시계, 아래 한 줄 범례, 갈래 내기(같은 세계 사본을 deepcopy 해 정책만 바꿔 돌림)와 결정성 확인.
더한 점: 두 칸(1920x1080), 무리 가까이 확대, 경보 겹침 둘 — (1) 경보를 낸 개체 자리에서 퍼지는 옅은 고리(약 0.5초, 들리는 거리
alarm_r 까지 커진다), (2) 남의 경보를 들은 개체의 가는 고리(경보를 쥐고 있는 동안).

세계: configs/v3_r2_w8_on.yaml (경보만 켠 세계), 시드 31000~ (관문·판정 시드 아님). 정책(손 규칙, 학습한 모델 없음):
  rbase : R_base(θ 4, a 0.9) — 위협이 보이고 4 안이거나 빠르게 다가오면 도망, 아니면 먹기 (경보를 읽지 않는다)
  look  : R_base + look 니치 — 위협이 안 보이는데 강한 경보(alarm_heard ≥ 0.4)를 들었고 은신처가 5 넘게 멀면 얼어붙어 경보 쪽을 본다

    python alarm_compare.py search  --seeds 31000 31039 --workers 6     # 후보 사건 찾기 -> cache/alarm_search.json
    python alarm_compare.py score   --top 40 --workers 6                # 후보마다 두 갈래를 돌려 물결 점수 -> cache/alarm_scored.json
    python alarm_compare.py sim     --pick 0                            # 고른 장면 기록 + 결정성 확인 -> cache/alarm_scene.pkl
    python alarm_compare.py stills  --secs 2 3 4 5                      # 확인용 정지 화면 (check/)
    python alarm_compare.py render                                      # alarm_compare.mp4 + 포스터 + 네 순간 띠
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(r"C:/kwon/univ/3-1/GameContentsCapstoneDesign/AdaptiveEcosystem/herbivore_rl")
CACHE = HERE / "cache" / "alarm"
CHECK = HERE / "check" / "alarm"
OUT = HERE
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
sys.dont_write_bytecode = True

import env.torch_init  # noqa: E402,F401  <- torch 보다 먼저

import numpy as np  # noqa: E402

from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import build_policy, forward_bind, forward_done  # noqa: E402
from env_v2 import world as W  # noqa: E402
from env_v2 import repertoire as REP  # noqa: E402

import repertoire_rules as rr  # noqa: E402

CONFIG = "configs/v3_r2_w8_on.yaml"
THETA, APPROACH = 4.0, 0.9
POLS = ("rbase", "look")
SEED_LO, SEED_HI = 31000, 31999
FORBIDDEN = set(range(12160, 12240)) | set(range(10200, 10220)) | set(range(10000, 10020)) | set(range(10100, 10120))

_orig_sp = W.World._step_predators_v3


def _sp_rec(self):
    caught = _orig_sp(self)
    self._sc_caught = caught.copy()
    return caught


W.World._step_predators_v3 = _sp_rec      # 이 프로세스 안에서만. 반환값을 복사할 뿐 동역학은 같다


def load_cfg():
    return rr.with_obs_extra(load_v2_config(ROOT / CONFIG))


def spec_of(cfg, name):
    spec = rr.rule_spec(cfg, THETA, APPROACH)
    if name == "look":
        spec["wrap"].append(rr.x_wrap(cfg, "look", "niche", None))
    return spec


def check_seed(seed):
    if not (SEED_LO <= seed <= SEED_HI) or seed in FORBIDDEN:
        raise ValueError(f"시드 {seed} 는 쓰지 않는다(31000~31999 만)")


def new_world(cfg, seed):
    check_seed(seed)
    return W.World(cfg, seeds=[seed])


def bound_policy(cfg, name, world, seed):
    p = build_policy(spec_of(cfg, name), seed)
    forward_bind(p, world)
    return p


def step(world, pol):
    a = pol(world.observe())
    _, _, done, _ = world.step(a)
    forward_done(pol, done)
    return done


# --------------------------------------------------------------------- #
# 1) 후보 찾기: R_base 로 돌리며 '위협을 본 개체가 낸 경보(홉 0, 비명 아님)를 위협을 못 본 채 먹던 이웃이 받은' 순간
# --------------------------------------------------------------------- #

QUIET = 40          # 사건 앞 이 스텝 동안 근처(QUIET_R)에 다른 경보가 없어야 한다(깨끗한 시작)
QUIET_R = 22.0
SEARCH_T = 3000


def _search_one(args):
    seed, T = args
    cfg = load_cfg()
    w = new_world(cfg, seed)
    pol = bound_policy(cfg, "rbase", w, seed)
    hist = []           # (t, 방출 위치들) 최근 QUIET 스텝
    out = []
    for _ in range(T):
        step(w, pol)
        t = int(w.t) - 1
        em = w._al_em
        emitted = np.flatnonzero(w.alarm_emit >= 0)
        if len(emitted):
            seen0 = [e for e in emitted if w.alarm_emit[e] == 0 and not em["cry"][e] and em["seen"][e]]
            for e in seen0:
                lis = np.flatnonzero(w.alarm_from == e)
                unseen = lis[(w._g["pred_count"][lis] == 0) & (w.behavior[lis] == REP.GRAZE)]
                quiet = all(np.min(np.linalg.norm(p - w.pos[e], axis=1)) > QUIET_R for (tt, p) in hist
                            if t - tt <= QUIET)
                if len(unseen) >= 2 and quiet and float(w.dark) < 0.15:
                    d = np.linalg.norm(w.pos - w.pos[e], axis=1)
                    out.append(dict(seed=seed, t=t, emitter=int(e), n_listen=int(len(lis)), n_unseen=int(len(unseen)),
                                    n_near16=int(np.sum(d <= 16.0)), threat=int(em["src_j"][e]),
                                    ptype=int(w.pred_type[em["src_j"][e]]) if em["src_j"][e] >= 0 else -1,
                                    pos=[float(v) for v in w.pos[e]], dark=float(w.dark), size=float(w.size)))
            hist.append((t, w.pos[emitted].copy()))
        hist = [(tt, p) for (tt, p) in hist if t - tt <= QUIET]
    return out


def _map(fn, jobs, workers):
    from concurrent.futures import ProcessPoolExecutor

    if workers <= 1:
        return [fn(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=min(workers, 8)) as ex:
        return list(ex.map(fn, jobs))


def cmd_search(args):
    CACHE.mkdir(parents=True, exist_ok=True)
    seeds = list(range(args.seeds[0], args.seeds[1] + 1))
    for s in seeds:
        check_seed(s)
    t1 = time.time()
    res = _map(_search_one, [(s, args.steps) for s in seeds], args.workers)
    cands = [c for r in res for c in r]
    cands.sort(key=lambda c: (-c["n_unseen"], -c["n_near16"]))
    (CACHE / "alarm_search.json").write_text(json.dumps(cands, indent=1), encoding="utf-8")
    print(f"search {len(seeds)} seeds {time.time() - t1:.0f}s -> {len(cands)} candidates", flush=True)
    for c in cands[:20]:
        print(c, flush=True)


# --------------------------------------------------------------------- #
# 2) 기록 (갈래 내기 + 결정성 확인)
# --------------------------------------------------------------------- #

LEAD = 22           # 사건 22스텝(2.9초) 앞에서 가른다
K = 105             # 갈래 길이 (14초)


def _frame(w, caught_pos, heard):
    g = w._g
    return dict(pos=w.pos.copy(), head=w.head.copy(), beh=w.behavior.astype(np.int8).copy(),
                phase=w.beh_phase.astype(np.int8).copy(), pred=w.pred_pos.copy(), ptype=w.pred_type.copy(),
                ranged=w.pred_ranged.copy(), stalk=w.stalk_state.copy(), pmode=w.player_mode.copy(),
                asleep=(w.pred_asleep.copy() if getattr(w, "pred_asleep", None) is not None
                        else np.zeros(w.M, dtype=bool)),
                food=w.food.copy(), dark=float(np.mean(w.dark)), caught=caught_pos, t=int(w.t),
                incov=w._in_cover(w.pos),
                # 경보 훅 (스텝 끝, 리스폰 전 값)
                al_level=np.asarray(w.alarm_level, dtype=np.float64).copy(),
                al_hop=np.asarray(w.alarm_hop).copy(), al_emit=np.asarray(w.alarm_emit).copy(),
                al_from=np.asarray(w.alarm_from).copy(), al_pt=np.asarray(w.alarm_pt).copy(),
                entry=np.asarray(w.entry_cause).copy(), seen=(np.asarray(g["pred_count"]) > 0).copy(),
                heard=heard.copy())


def _heard_update(w, heard):
    """'남의 경보를 들은' 표시: 남에게서 받아들이면 켠다. 경보가 꺼지거나(ttl 0) 스스로 본 위협으로 홉 0 을 내면 끈다."""
    h = heard.copy()
    h[np.asarray(w.alarm_from) >= 0] = True
    own0 = (np.asarray(w.alarm_emit) == 0) & (np.asarray(w.alarm_from) < 0)
    h[own0] = False
    h[np.asarray(w.alarm_level) <= 0.0] = False
    return h


def record_branch(cfg, snap, name, seed, k_steps=K):
    w = copy.deepcopy(snap)
    pol = bound_policy(cfg, name, w, seed)
    heard = np.zeros(w.N, dtype=bool)
    heard = _heard_update(w, heard)
    frames = [_frame(w, np.empty((0, 2)), heard)]
    frames[0]["done"] = np.zeros(w.N, dtype=bool)
    frames[0]["caught_slots"] = np.empty(0, dtype=np.int64)
    frames[0]["cry"] = np.zeros(w.N, dtype=bool)
    for _ in range(k_steps):
        pre = w.pos.copy()
        done = step(w, pol)
        c = w._sc_caught
        heard = _heard_update(w, heard)
        heard[done] = False
        f = _frame(w, pre[c], heard)
        f["done"] = done.copy()
        f["caught_slots"] = np.flatnonzero(c)
        f["cry"] = np.asarray(w._al_em["cry"]).copy() & (np.asarray(w.alarm_emit) >= 0)
        f["emit_pos"] = w.pos.copy()       # 방출 위치 = 스텝 끝 위치 (리스폰 전) — 리스폰 뒤 pos 와 다를 수 있어 아래에서 고친다
        frames.append(f)
    return frames


def traj_key(frames):
    return [np.concatenate([f["pos"].ravel(), f["pred"].ravel(), f["beh"].astype(np.float64), f["food"].ravel(),
                            f["al_level"].ravel(), f["al_emit"].astype(np.float64)])
            for f in frames]


def same_traj(a, b) -> bool:
    return len(a) == len(b) and all(np.array_equal(x, y) for x, y in zip(traj_key(a), traj_key(b)))


def snapshot_at(cfg, seed, t_split):
    w = new_world(cfg, seed)
    pol = bound_policy(cfg, "rbase", w, seed)
    for _ in range(t_split):
        step(w, pol)
    assert w.t == t_split
    return w, pol


def wave_score(fr_r, fr_l, c, hx, hy):
    """물결 점수 (look 갈래): 사건 뒤 4초 안에 '들어서(본 것 아님)' FREEZE 로 들어간 서로 다른 개체 수와 그 가운데 홉 1 로 들은 수,
    홉 1 중계 방출 수. rbase 갈래에서 같은 개체가 그 시각에 계속 먹었는지도 센다."""
    froze, froze_h1, relay = set(), set(), 0
    for k in range(LEAD, min(LEAD + 30, len(fr_l))):
        f, p = fr_l[k], fr_l[k - 1]
        m = in_win(f["pos"], c, hx, hy)
        into = (f["beh"] == REP.FREEZE) & (p["beh"] != REP.FREEZE) & m & ~f["done"]
        heard_in = into & ((f["entry"] & REP.ENTRY_HEARD) > 0) & ((f["entry"] & REP.ENTRY_SEEN) == 0)
        for i in np.flatnonzero(heard_in):
            froze.add(int(i))
            if f["al_hop"][i] >= 2:          # 홉 1 을 받고 중계하면 쥔 홉은 2 다
                froze_h1.add(int(i))
        relay += int(np.sum((f["al_emit"] >= 1) & m))
    graze_left = 0
    for i in froze:
        ks = range(LEAD, min(LEAD + 30, len(fr_r)))
        if all(fr_r[k]["beh"][i] == REP.GRAZE for k in ks):
            graze_left += 1
    catches_l = sum(int(np.sum(in_win(fr_l[k]["caught"], c, hx, hy))) for k in range(1, len(fr_l)) if len(fr_l[k]["caught"]))
    catches_r = sum(int(np.sum(in_win(fr_r[k]["caught"], c, hx, hy))) for k in range(1, len(fr_r)) if len(fr_r[k]["caught"]))
    return dict(froze=len(froze), froze_h1=len(froze_h1), relay=relay, graze_left=graze_left,
                catches_look=catches_l, catches_rbase=catches_r)


def _score_one(args):
    cand, = args
    cfg = load_cfg()
    seed, te = cand["seed"], cand["t"]
    t_split = te - LEAD
    snap, _ = snapshot_at(cfg, seed, t_split)
    fr_r = record_branch(cfg, snap, "rbase", seed, k_steps=LEAD + 45)
    fr_l = record_branch(cfg, snap, "look", seed, k_steps=LEAD + 45)
    c = cand["pos"]
    sc = wave_score(fr_r, fr_l, c, WIN_HX, WIN_HY)
    # 사건이 rbase 갈래에서 같은 스텝에 다시 일어났나 (frames[k] = 스텝 k 뒤, 사건 스텝 te 는 frames[LEAD + 1])
    sc["event_reproduced"] = bool(fr_r[LEAD + 1]["al_emit"][cand["emitter"]] == 0)
    # 두 갈래가 사건 전까지 같은가(look 이 사건 전에 이미 다른 행동을 하면 비교가 흐려진다)
    sc["same_until"] = next((k for k in range(len(fr_r)) if not np.array_equal(fr_r[k]["beh"], fr_l[k]["beh"])), None)
    def _diff_win(k):
        m = in_win(fr_r[k]["pos"], c, WIN_HX + 4, WIN_HY + 4) | in_win(fr_l[k]["pos"], c, WIN_HX + 4, WIN_HY + 4)
        return not np.array_equal(fr_r[k]["beh"][m], fr_l[k]["beh"][m])

    sc["same_until_win"] = next((k for k in range(len(fr_r)) if _diff_win(k)), None)
    # 홉 1 로 듣고 언 개체가 처음 방출원에서 얼마나 먼가(물결이 퍼진 거리)
    e0 = np.asarray(fr_r[LEAD + 1]["pos"][cand["emitter"]])
    far = 0.0
    for k in range(LEAD, min(LEAD + 30, len(fr_l))):
        f, p = fr_l[k], fr_l[k - 1]
        into = (f["beh"] == REP.FREEZE) & (p["beh"] != REP.FREEZE) & ((f["entry"] & REP.ENTRY_HEARD) > 0) &             ((f["entry"] & REP.ENTRY_SEEN) == 0)
        if into.any():
            far = max(far, float(np.max(np.linalg.norm(f["pos"][into] - e0, axis=1))))
    sc["wave_reach"] = round(far, 2)
    n_in = int(np.sum(in_win(fr_r[LEAD]["pos"], c, WIN_HX, WIN_HY)))
    sc["herd_in_win"] = n_in
    return dict(cand, **sc)


def cmd_score(args):
    cands = json.loads((CACHE / "alarm_search.json").read_text(encoding="utf-8"))
    cands = [c for c in cands if c["t"] - LEAD > 50][: args.top]
    t1 = time.time()
    res = _map(_score_one, [(c,) for c in cands], args.workers)
    res.sort(key=lambda r: (-(r["froze"] + 2 * r["froze_h1"] + r["graze_left"]), r["catches_look"]))
    (CACHE / "alarm_scored.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"score {len(cands)} {time.time() - t1:.0f}s", flush=True)
    for r in res[:25]:
        print({k: r[k] for k in ("seed", "t", "emitter", "ptype", "n_unseen", "n_near16", "froze", "froze_h1", "relay",
                                 "graze_left", "catches_look", "catches_rbase", "event_reproduced", "same_until",
                                 "same_until_win", "wave_reach", "herd_in_win")}, flush=True)


def cmd_sim(args):
    cfg = load_cfg()
    from replay_v2 import step_seconds

    step_sec = step_seconds(cfg)
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.seed is not None:
        pick = dict(seed=args.seed, t=args.t, emitter=args.emitter, pos=None)
    else:
        sc = json.loads((CACHE / "alarm_scored.json").read_text(encoding="utf-8"))
        pick = dict(sc[args.pick])
    seed, te = pick["seed"], pick["t"]
    check_seed(seed)
    t_split = te - LEAD
    t1 = time.time()
    w, pol = snapshot_at(cfg, seed, t_split)
    snap = copy.deepcopy(w)
    det, branches = {}, {}
    for p in POLS:
        a = record_branch(cfg, snap, p, seed)
        b = record_branch(cfg, snap, p, seed)
        det[f"{p}_two_copies_identical"] = same_traj(a, b)
        branches[p] = a
    # 원래 세계(R_base)를 이어 돌린 것과 rbase 갈래가 같은가
    cont = record_branch(cfg, w, "rbase", seed)          # w 자신을 deepcopy 해 이어 간다(같은 정책)
    det["rbase_branch_equals_original_run"] = same_traj(branches["rbase"], cont)
    det["look_branch_differs_from_rbase"] = not same_traj(branches["rbase"], branches["look"])
    det["same_until_step"] = next((k for k in range(K + 1)
                                   if not np.array_equal(branches["rbase"][k]["beh"], branches["look"][k]["beh"])), None)
    assert all(v for k, v in det.items() if k != "same_until_step"), det
    meta = dict(cov_c=np.asarray(snap.cov_c).copy(), cov_r=np.asarray(snap.cov_r).copy(), gw=int(snap.gw),
                food_cell=float(cfg.food_cell), size=float(snap.size), M=int(snap.M), N=int(snap.N),
                alarm_r=float(cfg.v2["features"]["alarm"]["alarm_r"]))
    if args.center:
        center = list(args.center)
    else:
        center = herd_center(branches, pick, meta)
    pick["center"] = center
    with open(CACHE / (args.cache or "alarm_scene.pkl"), "wb") as fh:
        pickle.dump(dict(pick=pick, meta=meta, branches=branches, det=det, step_sec=step_sec, t_split=t_split), fh)
    print(f"sim {time.time() - t1:.0f}s det={det} center={center} size={meta['size']:.1f}", flush=True)
    timeline(dict(pick=pick, meta=meta, branches=branches, det=det, step_sec=step_sec))


def herd_center(branches, pick, meta):
    fr = branches["look"]
    e = pick["emitter"]
    e0 = fr[LEAD + 1]["pos"][e].copy()
    pts = [e0]
    for k in range(LEAD, min(LEAD + 20, K)):
        f = fr[k]
        near = np.linalg.norm(f["pos"] - e0, axis=1) <= 18.0
        h = (f["heard"] | (f["al_emit"] >= 0)) & near
        if h.any():
            pts.append(np.median(f["pos"][h], axis=0))
    c = np.mean(np.stack(pts), axis=0)
    size = meta["size"]
    return [float(np.clip(c[0], WIN_HX, size - WIN_HX)), float(np.clip(c[1], WIN_HY, size - WIN_HY))]


def timeline(cache):
    """해설용: 0.27초(2스텝)마다 창 안 수 — 먹기·도망·얼어붙기, 경보를 들은 수, 이번 스텝 방출(홉별)."""
    c, step_sec = cache["pick"]["center"], cache["step_sec"]
    rows = []
    for k in range(0, K + 1):
        r = {"k": k, "sec": round(k * step_sec, 2)}
        for p in POLS:
            f = cache["branches"][p][k]
            m = in_win(f["pos"], c, WIN_HX, WIN_HY)
            bc = np.bincount(f["beh"][m].astype(np.int64), minlength=5)
            em = f["al_emit"][m]
            r[p] = dict(g=int(bc[0]), fl=int(bc[1]), hi=int(bc[2]), fz=int(bc[3]), heard=int(np.sum(f["heard"] & m)),
                        emit=[int(np.sum(em == h)) for h in range(3)], cry=int(np.sum(f["cry"] & m)) if "cry" in f else 0,
                        caught=int(np.sum(in_win(f["caught"], c, WIN_HX, WIN_HY))) if len(f["caught"]) else 0)
        rows.append(r)
    (CACHE / "alarm_timeline.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    for r in rows:
        if any(sum(r[p]["emit"]) or r[p]["caught"] for p in POLS) or r["k"] % 8 == 0:
            print(r["k"], r["sec"], "rbase", r["rbase"], "| look", r["look"], flush=True)


def load_cache(name=None):
    with open(CACHE / (name or "alarm_scene.pkl"), "rb") as fh:
        return pickle.load(fh)


# --------------------------------------------------------------------- #
# 화면 창
# --------------------------------------------------------------------- #

FIG_W, FIG_H, DPI = 19.2, 10.8, 100          # 1920 x 1080
ML, GAP = 0.25, 0.3
PW = (FIG_W - 2 * ML - GAP) / 2              # 9.2
PY0 = 0.95                                   # 패널 아래 끝 (범례 자리)
PH = 8.75
WIN_HX = 16.0
WIN_HY = WIN_HX * PH / PW


def in_win(p, c, hx=None, hy=None):
    p = np.asarray(p).reshape(-1, 2)
    hx = WIN_HX if hx is None else hx
    hy = WIN_HY if hy is None else hy
    return (np.abs(p[:, 0] - c[0]) <= hx) & (np.abs(p[:, 1] - c[1]) <= hy)


def clock(sec: float) -> str:
    s = int(max(sec, 0.0) + 1e-6)
    return f"{s // 60}:{s % 60:02d}"


# --------------------------------------------------------------------- #
# 그리기 (scenes_plain.MapPanel 사본 + 경보 겹침)
# --------------------------------------------------------------------- #

FIG_BG = "#1B2A2F"
FG = "#d9e0e2"
DOT = 380
TRAIL = 10
PTRAIL = 20
CATCH_SHOW = 14
FADE = 8
BEH_COLORS = ("#4cd964", "#ff9500", "#5f7cff", "#ffffff")
CHASER_C, STALKER_C, PLAYER_C, RANGED_C = "#ff2d2d", "#ffb020", "#00e5ff", "#ff2d2d"
COVER_EDGE = "#8a9ad8"
ALARM_C = "#ff6ec7"          # 경보 색 (다른 표식과 겹치지 않는 분홍)
RING_SEC = 0.55              # 퍼지는 고리가 보이는 시간
RING_R0 = 0.8

FPS = 30
HOLD0 = 30              # 처음 1초 멈춤
HOLD1 = 45              # 끝 1.5초 멈춤
HOLD_MID = 30           # 다시 보기 앞 1초 멈춤
HOLD_R0 = 15            # 다시 보기 처음 0.5초 멈춤
TITLE_FS = 32
CATCH_FS = 26
LEG_FS = 24
TITLES = {"rbase": "경보 무시 (직접 봐야 도망)", "look": "경보 들으면 고개 들기"}


def setup_font():
    import matplotlib
    import matplotlib.font_manager as fm

    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Malgun Gothic", "IBM Plex Sans KR", "NanumGothic", "AppleGothic"):
        if name in have:
            matplotlib.rcParams["font.family"] = name
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


class MapPanel:
    def __init__(self, ax, meta, frames, center, title, step_sec, hx=None, hy=None, dot=None, bang_off=0.62):
        from matplotlib.collections import LineCollection
        from matplotlib.colors import LinearSegmentedColormap
        from matplotlib.patches import Circle, Rectangle

        food_cmap = LinearSegmentedColormap.from_list("food", ["#2a2118", "#4a3b23", "#5d7a35", "#8fc44a"])
        self.ax, self.frames, self.c, self.meta, self.step_sec = ax, frames, center, meta, step_sec
        self.hx = WIN_HX if hx is None else hx
        self.hy = WIN_HY if hy is None else hy
        self.bang_off = bang_off
        self.k_min = 0
        self.dot = DOT if dot is None else dot
        D = self.dot
        ax.set_facecolor("#111111")
        ax.set_xlim(center[0] - self.hx, center[0] + self.hx)
        ax.set_ylim(center[1] - self.hy, center[1] + self.hy)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#4a5c62")
            s.set_linewidth(1.2)
        ax.set_title(title, color="white", fontsize=TITLE_FS, fontweight="bold", pad=14)
        f0 = frames[0]
        ext = (0, meta["gw"] * meta["food_cell"]) * 2
        self.food = ax.imshow(f0["food"], origin="lower", extent=ext, cmap=food_cmap, vmin=0.0, vmax=1.0,
                              interpolation="bilinear", zorder=0)
        for (cx, cy), cr in zip(meta["cov_c"], meta["cov_r"]):
            ax.add_patch(Circle((cx, cy), cr, facecolor="black", alpha=0.6, edgecolor=COVER_EDGE, linewidth=1.8,
                                zorder=1))
        self.night = ax.add_patch(Rectangle((center[0] - self.hx, center[1] - self.hy), 2 * self.hx, 2 * self.hy,
                                            facecolor="#000018", alpha=0.0, zorder=1.5, edgecolor="none"))
        self.trails = LineCollection([], linewidths=2.2, zorder=2, capstyle="round")
        ax.add_collection(self.trails)
        self.ptrails = LineCollection([], linewidths=2.6, zorder=2.2, capstyle="round")
        ax.add_collection(self.ptrails)
        # 경보: 퍼지는 고리(방출) — 반지름이 데이터 단위라 Circle 묶음으로 그린다
        self.rings = [Circle((0, 0), 1.0, facecolor="none", edgecolor=ALARM_C, linewidth=3.0, alpha=0.0, zorder=3.2)
                      for _ in range(24)]
        for r in self.rings:
            ax.add_patch(r)
        e = np.zeros((0, 2))
        # 들은 개체의 가는 고리 (점 바깥)
        self.heard = ax.scatter(e[:, 0], e[:, 1], marker="o", facecolors="none", edgecolors=ALARM_C,
                                s=D * 2.3, linewidths=2.2, zorder=3.9)
        self.herb = ax.scatter(e[:, 0], e[:, 1], s=D, zorder=4)
        self.bang = ax.scatter(e[:, 0], e[:, 1], marker="$!$", c="white", s=D * 1.3, linewidths=0.6,
                               edgecolors="white", zorder=4.6)
        kw = dict(edgecolors="white", linewidths=1.6, zorder=5)
        self.chaser = ax.scatter(e[:, 0], e[:, 1], marker="X", c=CHASER_C, s=D * 2.0, **kw)
        self.ranged = ax.scatter(e[:, 0], e[:, 1], marker="X", c=RANGED_C, s=D * 2.0, **kw)
        self.stalker = ax.scatter(e[:, 0], e[:, 1], marker="X", c=STALKER_C, s=D * 2.0, **kw)
        self.player = ax.scatter(e[:, 0], e[:, 1], marker="*", c=PLAYER_C, s=D * 3.2, edgecolors="black",
                                 linewidths=1.0, zorder=5.5)
        self.sleepy = ax.scatter(e[:, 0], e[:, 1], marker="X", c="#777777", s=D * 1.8, edgecolors="#bbbbbb",
                                 linewidths=1.0, zorder=5)
        self.catch_ring = ax.scatter(e[:, 0], e[:, 1], marker="o", facecolors="none", edgecolors="#ff2020",
                                     s=D * 4, linewidths=3.2, zorder=6)
        self.catch_txt = [ax.text(0, 0, "", color="#ff5050", fontsize=CATCH_FS, fontweight="bold", ha="center", va="top",
                                  zorder=7, clip_on=True) for _ in range(16)]
        n = len(frames[0]["pos"])
        self.last_done = np.full((len(frames), n), -10 ** 6, dtype=np.int64)
        cur = np.full(n, -10 ** 6, dtype=np.int64)
        for j, f in enumerate(frames):
            cur = np.where(f["done"], j, cur)
            self.last_done[j] = cur
        # 방출 목록: (스텝 j, 위치) — 방출 위치는 스텝 끝 위치(리스폰 전). 리스폰한 슬롯(잡힘 비명)은 잡힌 자리를 쓴다
        self.emits = []
        for j, f in enumerate(frames):
            if j == 0:
                continue
            for i in np.flatnonzero(f["al_emit"] >= 0):
                if f["done"][i]:
                    cs = list(f["caught_slots"])
                    p = f["caught"][cs.index(i)] if i in cs else frames[j - 1]["pos"][i]
                else:
                    p = f["pos"][i]
                self.emits.append((j, np.asarray(p, dtype=np.float64), int(f["al_emit"][i])))

    def update(self, k, frac=0.0):
        from matplotlib.colors import to_rgba

        fr = self.frames
        f = fr[k]
        nxt = fr[k + 1] if (frac > 0 and k + 1 < len(fr)) else None
        pos = f["pos"].copy()
        pred = f["pred"].copy()
        beh, phase = f["beh"], f["phase"]
        heard = f["heard"]
        if nxt is not None:
            ok = ~nxt["done"]
            pos[ok] = (1 - frac) * f["pos"][ok] + frac * nxt["pos"][ok]
            pred = (1 - frac) * f["pred"] + frac * nxt["pred"]
            beh, phase = nxt["beh"], nxt["phase"]
            heard = nxt["heard"]
        self.food.set_data(f["food"])
        self.night.set_alpha(0.5 * f["dark"])
        age = k - self.last_done[k]
        alpha = np.clip(0.2 + 0.8 * age / FADE, 0.2, 1.0)
        m = in_win(pos, self.c, self.hx + 1, self.hy + 1)
        bcol = np.array([to_rgba(c) for c in BEH_COLORS])
        cols = bcol[np.asarray(beh, dtype=np.int64)].copy()
        cols[:, 3] = alpha
        crouch = (beh == 2) & (phase == 1)
        edge = np.where(crouch[:, None], np.array(to_rgba("#e8f0ff")), np.array((0, 0, 0, 1.0)))
        edge[:, 3] = alpha
        self.herb.set_offsets(pos[m] if m.any() else np.empty((0, 2)))
        self.herb.set_facecolor(cols[m])
        self.herb.set_edgecolor(edge[m])
        self.herb.set_linewidths(np.where(crouch[m], 2.6, 1.0))
        fz = m & (beh == 3)
        self.bang.set_offsets(pos[fz] + np.array([self.bang_off, 1.05 * self.bang_off]) if fz.any() else np.empty((0, 2)))
        hm = m & heard
        self.heard.set_offsets(pos[hm] if hm.any() else np.empty((0, 2)))
        # 퍼지는 고리
        x = k + frac
        live = [(j, p, h) for (j, p, h) in self.emits if 0.02 < (x - (j - 1)) * self.step_sec < RING_SEC]
        R = self.meta["alarm_r"]
        for r, item in zip(self.rings, live[: len(self.rings)]):
            j, p, h = item
            u = (x - (j - 1)) * self.step_sec / RING_SEC          # 0 → 1
            r.set_center((p[0], p[1]))
            r.set_radius(RING_R0 + (R - RING_R0) * u)
            r.set_alpha(0.7 * (1.0 - u) ** 1.3)
            r.set_linewidth(3.0 - 1.8 * u)
        for r in self.rings[len(live):]:
            r.set_alpha(0.0)
        idx = np.flatnonzero(m)
        segs, scol = [], []
        for s in idx:
            pts = [pos[s]]
            for j in range(k, max(k - TRAIL, -1), -1):
                if j < k and fr[j + 1]["done"][s]:
                    break
                pts.append(fr[j]["pos"][s])
            if len(pts) > 2:
                segs.append(np.asarray(pts))
                c = bcol[int(beh[s])]
                scol.append((c[0], c[1], c[2], 0.5 * alpha[s]))
        self.trails.set_segments(segs)
        if scol:
            self.trails.set_color(scol)
        pt, asl = f["ptype"], f["asleep"]
        player = pt == W.PT_PLAYER
        stalker = (pt == W.PT_STALKER) & ~asl
        chaser = (pt == W.PT_CHASER) & ~f["ranged"] & ~asl
        ranged = (pt == W.PT_CHASER) & f["ranged"] & ~asl
        asleep = asl & ~player

        def off(mk):
            return pred[mk] if mk.any() else np.empty((0, 2))

        self.chaser.set_offsets(off(chaser))
        self.ranged.set_offsets(off(ranged))
        self.stalker.set_offsets(off(stalker))
        self.player.set_offsets(off(player))
        self.sleepy.set_offsets(off(asleep))
        psegs, pcols = [], []
        for i in range(len(pred)):
            pts = np.array([fr[j]["pred"][i] for j in range(max(k - PTRAIL, 0), k + 1)] + [pred[i]])
            if len(pts) > 2:
                psegs.append(pts)
                pcols.append((1.0, 0.45, 0.35, 0.55) if pt[i] != W.PT_PLAYER else (0.0, 0.9, 1.0, 0.55))
        self.ptrails.set_segments(psegs)
        if pcols:
            self.ptrails.set_color(pcols)
        cps = [fr[j]["caught"] for j in range(max(1, k - CATCH_SHOW + 1, self.k_min), k + 1) if len(fr[j]["caught"])]
        cps = np.concatenate(cps) if cps else np.empty((0, 2))
        cin = cps[in_win(cps, self.c, self.hx, self.hy)] if len(cps) else cps
        self.catch_ring.set_offsets(cin if len(cin) else np.empty((0, 2)))
        for j, tx in enumerate(self.catch_txt):
            if j < len(cin):
                tx.set_position((cin[j, 0], cin[j, 1] - 1.6 * self.bang_off))
                tx.set_text("잡힘")
            else:
                tx.set_text("")
        return self


def legend_handles():
    from matplotlib.legend_handler import HandlerTuple
    from matplotlib.lines import Line2D

    dot = dict(marker="o", ls="none", markersize=20, markeredgecolor="black", markeredgewidth=1.2)
    h = [Line2D([], [], markerfacecolor=BEH_COLORS[0], **dot),
         Line2D([], [], markerfacecolor=BEH_COLORS[1], **dot),
         (Line2D([], [], markerfacecolor=BEH_COLORS[3], **dot),
          Line2D([], [], marker="$!$", ls="none", markersize=20, color="white")),
         Line2D([], [], marker="X", ls="none", markersize=24, markerfacecolor=CHASER_C,
                markeredgecolor="white", markeredgewidth=1.6),
         Line2D([], [], marker="o", ls="none", markersize=30, markerfacecolor="none", markeredgecolor=ALARM_C,
                markeredgewidth=2.6, alpha=0.8),
         (Line2D([], [], marker="o", ls="none", markersize=28, markerfacecolor="none", markeredgecolor=ALARM_C,
                 markeredgewidth=2.0),
          Line2D([], [], markerfacecolor=BEH_COLORS[0], **dict(dot, markersize=17)))]
    labels = ["먹기", "도망", "얼어붙기(고개 듦)", "포식자", "경보 소리", "경보를 들음"]
    return h, labels, {tuple: HandlerTuple(ndivide=1, pad=0.0)}


def make_figure(cache):
    import matplotlib.pyplot as plt

    setup_font()
    pick, meta, branches = cache["pick"], cache["meta"], cache["branches"]
    fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI, facecolor=FIG_BG)
    panels = []
    for j, p in enumerate(POLS):
        ax = fig.add_axes(((ML + j * (PW + GAP)) / FIG_W, PY0 / FIG_H, PW / FIG_W, PH / FIG_H))
        panels.append(MapPanel(ax, meta, branches[p], pick["center"], TITLES[p], cache["step_sec"]))
    h, labels, hmap = legend_handles()
    fig.legend(handles=h, labels=labels, handler_map=hmap, loc="center left", ncol=len(h), fontsize=LEG_FS,
               frameon=False, labelcolor=FG, bbox_to_anchor=(ML / FIG_W, 0.5 * PY0 / FIG_H),
               handletextpad=0.4, columnspacing=1.6, handlelength=1.4)
    clk = fig.text((FIG_W - ML) / FIG_W, 0.5 * PY0 / FIG_H, "0:00", color=FG, fontsize=24, ha="right",
                   va="center", fontweight="bold")
    return fig, panels, clk


def draw_at(panels, clk, sec, step_sec):
    x = min(max(sec / step_sec, 0.0), float(K))
    k = int(np.floor(x + 1e-9))
    frac = x - k
    if k >= K:
        k, frac = K, 0.0
    for pnl in panels:
        pnl.update(k, frac)
    clk.set_text(clock(sec))


def cmd_stills(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CHECK.mkdir(exist_ok=True)
    cache = load_cache(args.cache)
    if args.center:
        cache["pick"]["center"] = list(args.center)
    fig, panels, clk = make_figure(cache)
    tag = (args.cache or "alarm_scene.pkl").replace(".pkl", "")
    for sec in args.secs:
        draw_at(panels, clk, sec, cache["step_sec"])
        out = CHECK / f"{tag}_t{sec:05.2f}.png"
        fig.savefig(str(out), dpi=DPI, facecolor=FIG_BG)
        print(out)
    plt.close(fig)


def cmd_render(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    from replay_v2 import _ffmpeg_exe, video_info

    cache = load_cache()
    step_sec = cache["step_sec"]
    fig, panels, clk = make_figure(cache)
    draw_at(panels, clk, args.poster, step_sec)
    png = OUT / "alarm_compare_poster.png"
    fig.savefig(str(png), dpi=DPI, facecolor=FIG_BG)
    total = K * step_sec
    t0, t1 = float(args.t0), float(min(args.t1, total))

    def run(a, b):
        n = int(round((b - a) * FPS))
        return [min(a + i / FPS, b) for i in range(n + 1)]

    secs = [t0] * HOLD0 + run(t0, t1)
    tags = [False] * len(secs)
    if args.replay:
        r0, r1 = args.replay
        secs += [t1] * HOLD_MID
        tags += [False] * HOLD_MID
        rr_ = [r0] * HOLD_R0 + run(r0, r1)
        secs += rr_
        tags += [True] * len(rr_)
        t_end = r1
    else:
        t_end = t1
    secs += [t_end] * HOLD1
    tags += [bool(args.replay)] * HOLD1
    rep_txt = fig.text((FIG_W - ML - 1.25) / FIG_W, 0.5 * PY0 / FIG_H, "", color="#ffe066", fontsize=24, ha="right",
                       va="center", fontweight="bold")

    def upd(i):
        draw_at(panels, clk, secs[i], step_sec)
        rep_txt.set_text("다시 보기" if tags[i] else "")
        return []

    matplotlib.rcParams["animation.ffmpeg_path"] = _ffmpeg_exe()
    writer = animation.FFMpegWriter(fps=FPS, codec="h264", bitrate=args.bitrate,
                                    extra_args=["-pix_fmt", "yuv420p", "-profile:v", "high", "-preset", "slow",
                                                "-movflags", "+faststart", "-threads", "4"])
    mp4 = OUT / "alarm_compare.mp4"
    tw = time.time()
    anim = animation.FuncAnimation(fig, upd, frames=len(secs), interval=1000 // FPS)
    anim.save(str(mp4), writer=writer, dpi=DPI, savefig_kwargs=dict(facecolor=FIG_BG))
    plt.close(fig)
    info = video_info(mp4)
    info.update(render_sec=round(time.time() - tw, 1), seed=cache["pick"]["seed"], t_split=cache["t_split"],
                event_step=cache["pick"]["t"], center=cache["pick"]["center"], half_x=WIN_HX, half_y=round(WIN_HY, 3),
                clock_sec=[t0, t1], replay_clock_sec=list(args.replay) if args.replay else None,
                hold_start_sec=HOLD0 / FPS, hold_mid_sec=HOLD_MID / FPS, hold_replay_start_sec=HOLD_R0 / FPS,
                hold_end_sec=HOLD1 / FPS, fps=FPS, speed=1.0, n_frames=len(secs),
                poster=str(png), poster_sec=args.poster, determinism=cache["det"],
                note="영상 시각 = 처음 멈춤(1초) + (화면 시계 − 구간 시작). 화면 시계는 갈라진 순간부터의 게임 시간(실시간 1배).")
    (OUT / "alarm_compare_video.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False), flush=True)


def cmd_strip(args):
    """네 순간 띠: 위 줄 경보 무시, 아래 줄 경보 들으면 고개 들기 (같은 네 시각). 시각 글자만 단다."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    setup_font()
    cache = load_cache()
    meta, br, c, step_sec = cache["meta"], cache["branches"], cache["pick"]["center"], cache["step_sec"]
    secs = args.secs
    n = len(secs)
    hx = args.hx
    hy = args.hy if args.hy else hx * PH / PW
    if args.center:
        c = list(args.center)
    cw, gap, lm, tm, bm = args.cw, 0.12, 0.85, 1.05, 0.85
    ch = cw * hy / hx
    W_in = lm + n * cw + (n - 1) * gap + 0.15
    H_in = tm + 2 * ch + gap + bm
    fig = plt.figure(figsize=(W_in, H_in), dpi=150, facecolor=FIG_BG)
    for row, p in enumerate(POLS):
        for j, sec in enumerate(secs):
            x0 = lm + j * (cw + gap)
            y0 = bm + (1 - row) * (ch + gap)
            ax = fig.add_axes((x0 / W_in, y0 / H_in, cw / W_in, ch / H_in))
            pnl = MapPanel(ax, meta, br[p], c, "", step_sec, hx=hx, hy=hy, dot=args.dot, bang_off=args.bang)
            x = sec / step_sec
            k = int(np.floor(x + 1e-9))
            pnl.update(k, x - k)
            if row == 0:
                cap = (args.captions[j] if args.captions and j < len(args.captions) else "")
                ax.set_title(f"{sec:.1f}초" + ("\n" + cap if cap else ""), color="white", fontsize=17,
                             fontweight="bold", pad=6)
        fig.text(0.45 / W_in, (bm + (1 - row) * (ch + gap) + ch / 2) / H_in,
                 "경보 무시" if p == "rbase" else "고개 들기", color="white", fontsize=17, fontweight="bold",
                 rotation=90, ha="center", va="center")
    h, labels, hmap = legend_handles()
    fig.legend(handles=h, labels=labels, handler_map=hmap, loc="center", ncol=len(h), fontsize=13,
               frameon=False, labelcolor=FG, bbox_to_anchor=(0.5, 0.45 * bm / H_in), handletextpad=0.3,
               columnspacing=1.2, handlelength=1.3, markerscale=0.6)
    out = OUT / "alarm_compare_strip.png"
    fig.savefig(str(out), dpi=150, facecolor=FIG_BG)
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--seeds", type=int, nargs=2, default=[31000, 31039])
    s.add_argument("--steps", type=int, default=SEARCH_T)
    s.add_argument("--workers", type=int, default=6)
    s1 = sub.add_parser("score")
    s1.add_argument("--top", type=int, default=40)
    s1.add_argument("--workers", type=int, default=6)
    s2 = sub.add_parser("sim")
    s2.add_argument("--pick", type=int, default=0)
    s2.add_argument("--seed", type=int)
    s2.add_argument("--t", type=int)
    s2.add_argument("--emitter", type=int)
    s2.add_argument("--center", type=float, nargs=2)
    s2.add_argument("--cache")
    s3 = sub.add_parser("stills")
    s3.add_argument("--secs", type=float, nargs="+", default=[2.0, 3.0, 3.5, 4.0, 5.0])
    s3.add_argument("--center", type=float, nargs=2)
    s3.add_argument("--cache")
    r = sub.add_parser("render")
    r.add_argument("--t0", type=float, default=0.0)
    r.add_argument("--t1", type=float, default=14.0)
    r.add_argument("--poster", type=float, default=3.6)
    r.add_argument("--bitrate", type=int, default=3800)
    r.add_argument("--replay", type=float, nargs=2, help="같은 구간을 실시간으로 한 번 더 (화면 시계 초)")
    st = sub.add_parser("strip")
    st.add_argument("--secs", type=float, nargs="+", default=[2.8, 3.2, 3.6, 4.4])
    st.add_argument("--hx", type=float, default=WIN_HX)
    st.add_argument("--dot", type=float, default=110)
    st.add_argument("--captions", nargs="*")
    st.add_argument("--hy", type=float)
    st.add_argument("--cw", type=float, default=4.6)
    st.add_argument("--bang", type=float, default=0.55)
    st.add_argument("--center", type=float, nargs=2)
    args = ap.parse_args()
    {"search": cmd_search, "score": cmd_score, "sim": cmd_sim, "stills": cmd_stills, "render": cmd_render,
     "strip": cmd_strip}[args.cmd](args)
