"""노려보기 대치 — 같은 순간, 두 갈래 근접 비교 영상 (발표용, 쉬운 표기).

원본: 5주차_자료/_build/scenes_plain.py (그 파일은 고치지 않는다. 이 파일은 그 사본을 고쳐 넓힌 것).
같은 그림 말(먹기 초록·도망 주황·숨기 파랑·얼어붙기 흰색 + '!', 포식자 X, 은신처 원, 작은 시계, 맑은 고딕)을 쓰고, 노려보기
규칙을 보이는 데 꼭 필요한 표시만 더했다: 노려보는 개체 → 포식자 가는 선, 멈춘 포식자 '멈칫', 물러나는 포식자 점선 화살표.

세계: configs/v3_r2_w7_on.yaml (노려보기 대치만 켠 관문 세계, 저장소 파일은 읽기만). 규칙(repertoire_rules, 읽기만):
  'rbase' = rule_spec(θ 4, a 0.9)                         — 가까우면 도망 (왼쪽 '노려보기 없음')
  'stare' = rule_spec(θ 4, a 0.9, x='stare', 'niche')     — + 노려보기 (유지 줄 포함, 오른쪽 '노려보기 있음')
갈래: 모두 'stare' 로 t0 까지 돌린 세계를 deepcopy 해서 왼쪽은 모두 'rbase', 오른쪽은 모두 'stare' 로 돌린다. 같은 정책의 두
사본이 비트 단위로 같은지, 오른쪽 갈래가 원래 실행의 이어 달리기와 같은지 확인한다. 시드는 31000~31999 만 쓴다.

    python stare_scenes.py scan   --seeds 31000 31023 --workers 6          # 사건 찾기 -> cache/scan_<kind>.json
    python stare_scenes.py probe  --kind stalker --top 30 --workers 6      # 후보의 왼쪽 갈래 미리 보기 -> cache/probe_<kind>.json
    python stare_scenes.py sim    --kind stalker --rank 12 --tag s12 --extra 10     # 갈래 + 결정성 -> cache/s12.pkl
    python stare_scenes.py stills --tag s12 --secs 0 2.5 3.2 5                       # 확인용 정지 화면 -> check/
    python stare_scenes.py render --tag s12 --t0 0 --t1 9.4 --poster 3.2 --name stare_compare
    python stare_scenes.py strip  --tag s12 --secs 1.5 3.2 5.5 7.2 --hx 12 --hy 10.8 --center 86.5 13.6 --dot 170
        --cap-left "몰래 다가옴" "계속 다가옴" "덮침" "둘 다 잡힘"
        --cap-right "몰래 다가옴" "노려봄 → 멈칫" "물러남" "둘 다 무사" --name stare_compare   (한 줄로 이어 쓴다)
    # 플레이어 대역(들키면 6초간 걷기만): 시드 31024~31183 을 다시 훑었다 (scan 은 cache/scan_*.json 을 덮는다 —
    # 처음 훑은 31000~31023 결과는 cache/scan_*_31000-31023.json 에 복사해 두었다)
    python stare_scenes.py scan   --seeds 31024 31183 --workers 6
    python stare_scenes.py probe  --kind player --top 15 --workers 6
    python stare_scenes.py sim    --kind player --rank 0 --tag p0 --shift 3 --nudge 1.5 3.5
    python stare_scenes.py render --tag p0 --t0 2.0 --t1 9.2 --poster 6.4 --name stare_player_compare
    # (t0 2.0: 화면 시계 2.0초에 창 안의 두 마리가 굶어 죽어 사라지므로 그 뒤에서 시작한다. 검토 때 1.0 -> 2.0)
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
CACHE = HERE / "cache"
CHECK = HERE / "check"
OUT = HERE
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import numpy as np  # noqa: E402

from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import build_policy, forward_bind, forward_done  # noqa: E402
from env_v2 import world as W  # noqa: E402
import repertoire_rules as rr  # noqa: E402

CONFIG = "configs/v3_r2_w7_on.yaml"
THETA, APPROACH = 4.0, 0.9
SEED_LO, SEED_HI = 31000, 31999
SCAN_STEPS = 3000
GRAZE, FLEE, HIDE, FREEZE, SLEEP = 0, 1, 2, 3, 4

POLS = ("rbase", "stare")
TITLES = {"rbase": "노려보기 없음", "stare": "노려보기 있음"}
BEH_KO = ("먹기", "도망", "숨기", "얼어붙기")

_orig_sp = W.World._step_predators_v3


def _sp_rec(self):
    caught = _orig_sp(self)
    self._sc_caught = caught.copy()
    return caught


W.World._step_predators_v3 = _sp_rec      # 이 프로세스 안에서만. 반환값을 복사할 뿐 동역학은 같다


def check_seed(s: int) -> int:
    s = int(s)
    if not (SEED_LO <= s <= SEED_HI):
        raise ValueError(f"시드는 {SEED_LO}~{SEED_HI} 만 쓴다(관문·판정 시드와 겹치지 않게). 받은 값: {s}")
    return s


def load_cfg():
    return rr.with_obs_extra(load_v2_config(ROOT / CONFIG))


def spec_of(cfg, name):
    if name == "rbase":
        return rr.rule_spec(cfg, THETA, APPROACH)
    if name == "stare":
        return rr.rule_spec(cfg, THETA, APPROACH, x="stare", mode="niche")
    raise ValueError(name)


def new_world(cfg, seed):
    return W.World(cfg, seeds=[check_seed(seed)])


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
# 사건 찾기 (모두 'stare' 규칙, 시드마다 SCAN_STEPS)
# --------------------------------------------------------------------- #

HX, HY = 15.0, 10.5          # 사건 찾기 창 반폭·반높이 (30 x 21 단위)
VIEW_HY = 13.0               # 영상 창 반높이 (30 x 26 단위 — 화면 세로를 채운다)
MARGIN = 2.0                 # 창 가장자리 여유
LEAD = 22                    # 대치 시작 몇 스텝 앞에서 가른다 (2.9초)
TAIL = 34                    # 물러남 시작 뒤 몇 스텝까지 보인다 (4.5초)
P_LEAD = 30                  # 플레이어: 들킴 몇 스텝 앞에서 가른다 (4초)
P_TAIL = 70                  # 플레이어: 들킴 뒤 몇 스텝까지 (9.3초)


def _scan_one(args):
    seed, steps = args
    cfg = load_cfg()
    w = new_world(cfg, seed)
    pol = bound_policy(cfg, "stare", w, seed)
    T, N, M = steps, w.N, w.M
    pos = np.zeros((T + 1, N, 2), np.float32)
    pred = np.zeros((T + 1, M, 2), np.float32)
    beh = np.zeros((T + 1, N), np.int8)
    st = np.zeros((T + 1, M), np.int8)
    lock = np.full((T + 1, M), -1, np.int32)
    pmode = np.zeros((T + 1, M), np.int8)
    spl = np.zeros((T + 1, M), np.int16)
    spc = np.zeros((T + 1, M), bool)
    asl = np.zeros((T + 1, M), bool)
    done = np.zeros((T + 1, N), bool)
    caught = np.zeros((T + 1, N), bool)
    incov = np.zeros((T + 1, N), bool)
    stare = np.full((T + 1, N), -1, np.int32)
    dark = np.zeros(T + 1)

    def rec(i):
        pos[i], pred[i], beh[i] = w.pos, w.pred_pos, w.behavior
        st[i], lock[i], pmode[i] = w.stalk_state, w.pred_lock, w.player_mode
        spl[i], spc[i] = w.spotted_left, w.spotted_charge
        asl[i] = w.pred_asleep if getattr(w, "pred_asleep", None) is not None else False
        incov[i] = w._in_cover(w.pos)
        stare[i] = w.stare_by
        dark[i] = float(np.mean(w.dark))

    rec(0)
    for i in range(1, T + 1):
        d = step(w, pol)
        rec(i)
        done[i] = d
        caught[i] = w._sc_caught
    size = float(w.size)
    ptype = w.pred_type.copy()
    is_player = w.pred_is_player.copy()
    D = dict(pos=pos, pred=pred, beh=beh, st=st, lock=lock, pmode=pmode, spl=spl, spc=spc, asl=asl, done=done,
             caught=caught, incov=incov, stare=stare, dark=dark, size=size)
    ev_s, ev_p = [], []
    for m in np.flatnonzero(ptype == W.PT_STALKER):
        for i in np.flatnonzero((st[:-1, m] == W.ST_STANDOFF) & (st[1:, m] == W.ST_BALK)) + 1:
            k = int(lock[i - 1, m])
            j = i - 1
            while j > 0 and st[j - 1, m] == W.ST_STANDOFF:
                j -= 1
            e = _metrics_stalker(D, seed, int(m), k, int(j), int(i))
            if e is not None:
                ev_s.append(e)
    for m in np.flatnonzero(is_player):
        for i in np.flatnonzero((spl[:-1, m] == 0) & (spl[1:, m] > 0)) + 1:
            ks = np.flatnonzero(stare[i] == m)
            if len(ks) == 0:
                continue
            e = _metrics_player(D, seed, int(m), int(ks[0]), int(i))
            if e is not None:
                ev_p.append(e)
    return dict(seed=seed, size=size, M=int(M), stalker=ev_s, player=ev_p)


def _window(pts, size):
    lo, hi = pts.min(0), pts.max(0)
    ext = hi - lo
    fits = bool(ext[0] <= 2 * (HX - MARGIN) and ext[1] <= 2 * (HY - MARGIN))
    c = 0.5 * (lo + hi)
    c = np.array([np.clip(c[0], HX, size - HX), np.clip(c[1], HY, size - HY)])
    inside = bool(np.all(np.abs(pts - c) <= np.array([HX - 0.8, HY - 0.8])))
    return c, fits and inside


def _inwin(p, c, hx=HX, hy=HY):
    p = np.asarray(p).reshape(-1, 2)
    return (np.abs(p[:, 0] - c[0]) <= hx) & (np.abs(p[:, 1] - c[1]) <= hy)


def _crowd(D, c, k0, k1, k, m):
    """창 안 다른 초식 수(평균·최대), 다른 포식자가 창에 있던 스텝 수, 잡힘 수(창 안)."""
    n_in, oth, catch_in = [], 0, 0
    for i in range(k0, k1 + 1):
        a = _inwin(D["pos"][i], c)
        a[k] = False
        n_in.append(int(a.sum()))
        b = _inwin(D["pred"][i], c)
        b[m] = False
        oth += int(b.any())
        if i > k0:
            catch_in += int(np.sum(D["caught"][i] & _inwin(D["pos"][i - 1], c)))
    return float(np.mean(n_in)), int(np.max(n_in)), oth, catch_in


def _metrics_stalker(D, seed, m, k, ts, tb):
    k0, k1 = ts - LEAD, tb + TAIL
    T = len(D["dark"]) - 1
    if k0 < 1 or k1 > T or k < 0:
        return None
    if D["done"][k0 + 1:k1 + 1, k].any():
        return None
    pts = np.concatenate([D["pred"][k0:k1 + 1, m], D["pos"][k0:k1 + 1, k]])
    c, ok = _window(pts.astype(np.float64), D["size"])
    cm, cx, oth, cin = _crowd(D, c, k0, k1, k, m)
    d_s = float(np.linalg.norm(D["pred"][ts, m] - D["pos"][ts, k]))
    d_0 = float(np.linalg.norm(D["pred"][k0, m] - D["pos"][k0, k]))
    others = np.delete(D["pos"][ts:tb + 1], k, axis=1)
    near = float(np.min(np.linalg.norm(others - D["pos"][ts:tb + 1, k][:, None, :], axis=2)))
    pp = D["pred"][k0:k1 + 1, m]
    wall = float(min(pp.min(), (D["size"] - pp).min()))
    bdir = D["pred"][tb, m] - D["pos"][tb, k]
    bdir = bdir / max(np.linalg.norm(bdir), 1e-9)
    return dict(seed=seed, m=m, k=k, ts=ts, tb=tb, k0=k0, k1=k1, center=[float(c[0]), float(c[1])], fits=ok,
                crowd_mean=cm, crowd_max=cx, other_pred_steps=oth, catch_in_win=cin, d_standoff=d_s, d_start=d_0,
                nearest_kin=near, wall_min=wall, dark_max=float(D["dark"][k0:k1 + 1].max()),
                beh_k0=int(D["beh"][k0, k]), lock_k0=int(D["lock"][k0, m]), st_k0=int(D["st"][k0, m]),
                incov_ts=bool(D["incov"][ts, k]), balk_dir=[float(bdir[0]), float(bdir[1])],
                standoff_steps=int(tb - ts), caught_k_after=bool(D["caught"][tb:k1 + 1, k].any()))


def _metrics_player(D, seed, m, k, tsp):
    k0, k1 = tsp - P_LEAD, tsp + P_TAIL
    T = len(D["dark"]) - 1
    if k0 < 1 or k1 > T:
        return None
    if D["done"][k0 + 1:k1 + 1, k].any():
        return None
    ch = np.flatnonzero((D["pmode"][tsp:k1 + 1, m] == W.PM_CHARGE) & D["spc"][tsp:k1 + 1, m])
    t_ch = int(tsp + ch[0]) if len(ch) else -1
    pts = np.concatenate([D["pred"][k0:k1 + 1, m], D["pos"][k0:k1 + 1, k]])
    c, ok = _window(pts.astype(np.float64), D["size"])
    cm, cx, oth, cin = _crowd(D, c, k0, k1, k, m)
    d_sp = float(np.linalg.norm(D["pred"][tsp, m] - D["pos"][tsp, k]))
    return dict(seed=seed, m=m, k=k, tsp=tsp, k0=k0, k1=k1, t_charge=t_ch, center=[float(c[0]), float(c[1])], fits=ok,
                crowd_mean=cm, crowd_max=cx, other_pred_steps=oth, catch_in_win=cin, d_spot=d_sp,
                dark_max=float(D["dark"][k0:k1 + 1].max()), beh_k0=int(D["beh"][k0, k]),
                lock_k0=int(D["lock"][k0, m]), pmode_k0=int(D["pmode"][k0, m]),
                caught_k=bool(D["caught"][tsp:k1 + 1, k].any()))


def score_stalker(e):
    s = 0.0
    s -= 6.0 * e["other_pred_steps"] / 10.0
    s -= abs(e["crowd_mean"] - 4.0) * 0.6
    s -= 4.0 * (e["crowd_max"] > 10)
    s -= 3.0 * (e["nearest_kin"] < 1.5)
    s -= 2.0 * abs(e["d_standoff"] - 7.0) / 2.0
    s += 2.0 * abs(e["balk_dir"][0])            # 창이 가로로 길다: 가로로 물러나면 오래 보인다
    s -= 5.0 * e["incov_ts"]
    s -= 4.0 * (e["wall_min"] < 2.0)
    s -= 3.0 * e["catch_in_win"]
    return s


def stalker_ok(e):
    return (e["fits"] and e["dark_max"] <= 0.05 and e["beh_k0"] == GRAZE and e["lock_k0"] == e["k"]
            and e["st_k0"] == W.ST_ROAM and not e["caught_k_after"] and e["standoff_steps"] >= 5)


def score_player(e):
    s = 0.0
    s -= 6.0 * e["other_pred_steps"] / 10.0
    s -= abs(e["crowd_mean"] - 4.0) * 0.6
    s -= 3.0 * e["catch_in_win"]
    s += 3.0 * (e["t_charge"] >= 0)
    return s


def player_ok(e):
    return e["fits"] and e["dark_max"] <= 0.05 and e["beh_k0"] == GRAZE and not e["caught_k"]


def cmd_scan(args):
    from concurrent.futures import ProcessPoolExecutor

    CACHE.mkdir(parents=True, exist_ok=True)
    seeds = list(range(check_seed(args.seeds[0]), check_seed(args.seeds[1]) + 1))
    t1 = time.time()
    with ProcessPoolExecutor(max_workers=min(args.workers, 8)) as ex:
        res = list(ex.map(_scan_one, [(s, args.steps) for s in seeds]))
    ev_s = [e for r in res for e in r["stalker"]]
    ev_p = [e for r in res for e in r["player"]]
    for e in ev_s:
        e["ok"], e["score"] = bool(stalker_ok(e)), float(score_stalker(e))
    for e in ev_p:
        e["ok"], e["score"] = bool(player_ok(e)), float(score_player(e))
    ev_s.sort(key=lambda e: (not e["ok"], -e["score"]))
    ev_p.sort(key=lambda e: (not e["ok"], -e["score"]))
    meta = dict(config=CONFIG, seeds=[seeds[0], seeds[-1]], steps=args.steps, lead=LEAD, tail=TAIL, hx=HX, hy=HY,
                elapsed_s=round(time.time() - t1, 1))
    (CACHE / "scan_stalker.json").write_text(json.dumps(dict(meta=meta, events=ev_s), indent=1), encoding="utf-8")
    (CACHE / "scan_player.json").write_text(json.dumps(dict(meta=meta, events=ev_p), indent=1), encoding="utf-8")
    print(f"scan {time.time() - t1:.0f}s: stalker balk {len(ev_s)} (ok {sum(e['ok'] for e in ev_s)}), "
          f"player spotted {len(ev_p)} (ok {sum(e['ok'] for e in ev_p)})")
    for e in ev_s[:12]:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.items() if k not in ("center",)})
    for e in ev_p[:6]:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.items() if k not in ("center",)})


# --------------------------------------------------------------------- #
# 갈래 기록 (원본 record_branch + 노려보기 훅)
# --------------------------------------------------------------------- #


def _frame(w, caught_pos):
    return dict(pos=w.pos.copy(), head=w.head.copy(), beh=w.behavior.astype(np.int8).copy(),
                phase=w.beh_phase.astype(np.int8).copy(), pred=w.pred_pos.copy(), phead=w.pred_head.copy(),
                ptype=w.pred_type.copy(), ranged=w.pred_ranged.copy(), stalk=w.stalk_state.copy(),
                stalk_left=w.stalk_left.copy(), pmode=w.player_mode.copy(),
                asleep=(w.pred_asleep.copy() if getattr(w, "pred_asleep", None) is not None
                        else np.zeros(w.M, dtype=bool)),
                food=w.food.copy(), dark=float(np.mean(w.dark)), caught=caught_pos, t=int(w.t),
                incov=w._in_cover(w.pos), stare_by=w.stare_by.copy(), lock=w.pred_lock.copy(),
                spot_cnt=w.spot_cnt.copy(), balk_dir=w.balk_dir.copy(), spotted_left=w.spotted_left.copy(),
                spotted_charge=w.spotted_charge.copy(), pvel=w.pred_vel.copy())


def record_branch(cfg, snap, name, seed, k_steps):
    w = copy.deepcopy(snap)
    pol = bound_policy(cfg, name, w, seed)
    frames = [_frame(w, np.empty((0, 2)))]
    frames[0]["done"] = np.zeros(w.N, dtype=bool)
    frames[0]["caught_slots"] = np.empty(0, dtype=np.int64)
    for _ in range(k_steps):
        pre = w.pos.copy()
        done = step(w, pol)
        c = w._sc_caught
        f = _frame(w, pre[c])
        f["done"] = done.copy()
        f["caught_slots"] = np.flatnonzero(c)
        frames.append(f)
    return frames


TRAJ_KEYS = ("pos", "head", "pred", "phead", "beh", "phase", "food", "stalk", "lock", "stare_by", "spot_cnt",
             "spotted_left", "pmode")


def traj_key(frames):
    return [np.concatenate([np.asarray(f[k], dtype=np.float64).ravel() for k in TRAJ_KEYS]) for f in frames]


def same_traj(a, b) -> bool:
    return len(a) == len(b) and all(np.array_equal(x, y) for x, y in zip(traj_key(a), traj_key(b)))


def _pick(kind, rank, scan_rank=False):
    """probe 결과(있으면)의 순서, 없으면 scan 순서에서 rank 번째."""
    pp = CACHE / f"probe_{kind}.json"
    if pp.exists() and not scan_rank:
        return json.loads(pp.read_text(encoding="utf-8"))["events"][rank]
    return json.loads((CACHE / f"scan_{kind}.json").read_text(encoding="utf-8"))["events"][rank]


def _probe_one(args):
    """후보 하나: t0 까지 돌려 왼쪽('rbase') 갈래만 짧게 돌려 본다 — 같은 포식자가 덮치는지, 표적이 잡히는지."""
    kind, e = args
    cfg = load_cfg()
    seed, m, k, k0, k1 = e["seed"], e["m"], e["k"], e["k0"], e["k1"]
    w = new_world(cfg, seed)
    pol = bound_policy(cfg, "stare", w, seed)
    for _ in range(k0):
        step(w, pol)
    fr = record_branch(cfg, w, "rbase", seed, k1 - k0)
    dmin, pounce, caught_k, caught_win = 1e9, False, -1, 0
    c = np.asarray(e["center"])
    for j, f in enumerate(fr[1:], 1):
        dmin = min(dmin, float(np.linalg.norm(f["pred"][m] - f["pos"][k])))
        if kind == "stalker":
            pounce |= bool(f["stalk"][m] == W.ST_POUNCE)
        else:
            pounce |= bool(f["pmode"][m] == W.PM_CHARGE)
        if k in f["caught_slots"] and caught_k < 0:
            caught_k = j
        caught_win += int(np.sum(_inwin(f["caught"], c)))
    e = dict(e, left_dmin=dmin, left_pounce=pounce, left_caught_k_step=caught_k, left_caught_in_win=caught_win)
    return e


def cmd_probe(args):
    from concurrent.futures import ProcessPoolExecutor

    sc = json.loads((CACHE / f"scan_{args.kind}.json").read_text(encoding="utf-8"))
    cand = [e for e in sc["events"] if e["ok"]][:args.top]
    with ProcessPoolExecutor(max_workers=min(args.workers, 8)) as ex:
        res = list(ex.map(_probe_one, [(args.kind, e) for e in cand]))
    for e in res:
        e["score2"] = e["score"] + (4.0 if e["left_caught_k_step"] > 0 else 0.0) + (1.5 if e["left_pounce"] else 0.0)
    res.sort(key=lambda e: -e["score2"])
    (CACHE / f"probe_{args.kind}.json").write_text(json.dumps(dict(meta=sc["meta"], events=res), indent=1),
                                                   encoding="utf-8")
    for i, e in enumerate(res):
        print(i, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.items()
                  if k in ("seed", "m", "k", "ts", "tb", "tsp", "t_charge", "k0", "crowd_mean", "crowd_max",
                           "other_pred_steps", "d_standoff", "d_spot", "nearest_kin", "left_dmin", "left_pounce",
                           "left_caught_k_step", "left_caught_in_win", "score2", "balk_dir")})


def cmd_sim(args):
    from replay_v2 import step_seconds

    cfg = load_cfg()
    step_sec = step_seconds(cfg)
    e = _pick(args.kind, args.rank)
    tag = args.tag or args.kind
    seed, k0, k1 = e["seed"], e["k0"], e["k1"]
    K = k1 - k0 + args.extra
    t1 = time.time()
    w = new_world(cfg, seed)
    pol = bound_policy(cfg, "stare", w, seed)
    for _ in range(k0):
        step(w, pol)
    assert w.t == k0, (w.t, k0)
    snap = copy.deepcopy(w)
    det, branches = {}, {}
    for p in POLS:
        a = record_branch(cfg, snap, p, seed, K)
        b = record_branch(cfg, snap, p, seed, K)
        det[f"{p}_two_copies_identical"] = same_traj(a, b)
        branches[p] = a
    cont = [_frame(w, np.empty((0, 2)))]
    for _ in range(K):
        step(w, pol)
        cont.append(_frame(w, np.empty((0, 2))))
    det["stare_branch_equals_original_run"] = same_traj(branches["stare"], cont)
    det["rbase_branch_differs_from_stare"] = not same_traj(branches["rbase"], branches["stare"])
    first_diff = next((j for j, (x, y) in enumerate(zip(traj_key(branches["rbase"]), traj_key(branches["stare"])))
                       if not np.array_equal(x, y)), None)
    assert all(det.values()), det
    e["center"] = view_center(args, e, branches["stare"], float(snap.size))
    meta = dict(cov_c=np.asarray(snap.cov_c).copy(), cov_r=np.asarray(snap.cov_r).copy(), gw=int(snap.gw),
                food_cell=float(cfg.food_cell), size=float(snap.size), M=int(snap.M), N=int(snap.N))
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / f"{tag}.pkl", "wb") as fh:
        pickle.dump(dict(pick=e, meta=meta, branches=branches, det=det, step_sec=step_sec, K=K, kind=args.kind), fh)
    tl = timeline(args.kind, e, branches, step_sec)
    stats = dict(kind=args.kind, tag=tag, pick=e, K=K, step_sec=step_sec, clip_sec=round(K * step_sec, 2),
                 window=dict(center=e["center"], half_x=HX, half_y=VIEW_HY),
                 determinism=det, first_differing_frame=first_diff, world_size=meta["size"], timeline=tl)
    (CACHE / f"{tag}_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1, default=str),
                                                 encoding="utf-8")
    print(f"sim {tag}: {time.time() - t1:.0f}s det={det} first_diff={first_diff} K={K}")
    for row in tl:
        print(row)


def view_center(args, e, frames, size):
    """영상 창 가운데. 기본: 사건 순간(대치 시작·들킴)의 표적 자리에서 '표적 → 위협' 쪽으로 args.shift 만큼 옮긴 점 —
    표적과 무리가 창 한쪽에 들고, 물러나는 위협은 끝 무렵 창 밖으로 걸어 나간다. 세계 밖으로 나가지 않게 자른다."""
    if args.center:
        c = np.asarray(args.center, dtype=np.float64)
    else:
        m, k = e["m"], e["k"]
        j = (e["ts"] if "ts" in e else e["tsp"]) - e["k0"]
        f = frames[j]
        v = f["pred"][m] - f["pos"][k]
        u = v / max(np.linalg.norm(v), 1e-9)
        c = f["pos"][k] + args.shift * u + np.asarray(args.nudge, dtype=np.float64)
    return [float(np.clip(c[0], HX, size - HX)), float(np.clip(c[1], VIEW_HY, size - VIEW_HY))]


def timeline(kind, e, branches, step_sec):
    """주인공 포식자 m·표적 k 의 상태가 바뀌는 순간 (화면 시계 초). 해설용."""
    m, k = e["m"], e["k"]
    rows = []
    for p in POLS:
        fr = branches[p]
        prev = None
        for j, f in enumerate(fr):
            dist = float(np.linalg.norm(f["pred"][m] - f["pos"][k]))
            s = (int(f["stalk"][m]) if kind == "stalker" else int(f["pmode"][m]), int(f["beh"][k]),
                 int(f["stare_by"][k] == m), int(f["spotted_left"][m] > 0), int(f["spotted_charge"][m]))
            caught = bool(k in f["caught_slots"])
            if s != prev or caught:
                rows.append(dict(branch=p, step=j, sec=round(j * step_sec, 2),
                                 pred_state=(["배회·잠행", "덮침", "탈진", "멈칫(대치)", "물러남"][s[0]] if kind == "stalker"
                                             else ["배회", "잠행", "돌진", "휴식"][s[0]]),
                                 target_beh=["먹기", "도망", "숨기", "얼어붙기", "잠"][s[1]], staring=bool(s[2]),
                                 spotted=bool(s[3]), slow_charge=bool(s[4]), dist=round(dist, 2), caught=caught,
                                 pred_speed=round(float(np.linalg.norm(f["pvel"][m])), 3)))
                prev = s
    return rows


def load_cache(tag):
    with open(CACHE / f"{tag}.pkl", "rb") as fh:
        return pickle.load(fh)


# --------------------------------------------------------------------- #
# 그리기 (원본 MapPanel + 노려보기 표시)
# --------------------------------------------------------------------- #

FIG_W, FIG_H, DPI = 19.2, 10.8, 100          # 1920 x 1080
FIG_BG = "#1B2A2F"
FG = "#d9e0e2"
DOT = 430                                     # 초식 점 (pt^2) — 30단위 창이라 원본보다 크다
TRAIL = 10
PTRAIL = 20
CATCH_SHOW = 14
FADE = 8
BEH_COLORS = ("#4cd964", "#ff9500", "#5f7cff", "#ffffff")
CHASER_C, STALKER_C, PLAYER_C, RANGED_C = "#ff2d2d", "#ffb020", "#00e5ff", "#ff2d2d"
COVER_EDGE = "#8a9ad8"
STARE_C = "#fff27a"                           # 노려보는 선 (옅은 노랑)
MARK_C = "#ffe36b"                            # '멈칫'·'물러남' 글자와 화살표

FPS = 30
HOLD0 = 30              # 처음 1초 멈춤
HOLD1 = 45              # 끝 1.5초 멈춤

ML, GAP = 0.25, 0.3
PW = (FIG_W - 2 * ML - GAP) / 2                         # 9.2
PH = PW * VIEW_HY / HX                                  # 7.67
PY0 = 1.15                                              # 패널 아래 끝
TITLE_FS = 34
CATCH_FS = 26
MARK_FS = 22
LEG_FS = 25
STARE_HOLD = 3          # 노려보기가 끝난 뒤 선이 사라지는 스텝 수 (0.4초)
# 갈래 안에서 죽은(잡힘·굶음) 슬롯은 세계 규칙상 무작위 자리에 새 개체로 다시 놓인다. 근접 창 안에 우연히 떨어지면
# '잡힌 개체가 살아났다'처럼 보이므로(s12 왼쪽 7.07초: 잡힌 자리에서 약 3단위), 영상·띠·정지 화면에서는 그리지 않는다.
# 동역학·결정성 확인과는 무관한 그리기 선택이다.
HIDE_RESPAWNED = True


def setup_font():
    import matplotlib
    import matplotlib.font_manager as fm

    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Malgun Gothic", "IBM Plex Sans KR", "NanumGothic", "AppleGothic"):
        if name in have:
            matplotlib.rcParams["font.family"] = name
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


def in_win(p, c, hx=HX, hy=HY):
    return _inwin(p, c, hx, hy)


def clock(sec: float) -> str:
    s = int(max(sec, 0.0) + 1e-6)
    return f"{s // 60}:{s % 60:02d}"


class MapPanel:
    def __init__(self, ax, meta, frames, center, title, hx=HX, hy=VIEW_HY, dot=DOT, bang_off=0.75, marks=True,
                 fs_scale=1.0, lw_scale=1.0):
        from matplotlib.collections import LineCollection
        from matplotlib.colors import LinearSegmentedColormap
        from matplotlib.patches import Circle, Rectangle

        food_cmap = LinearSegmentedColormap.from_list("food", ["#2a2118", "#4a3b23", "#5d7a35", "#8fc44a"])
        self.ax, self.frames, self.c = ax, frames, center
        self.hx, self.hy, self.bang_off, self.marks = hx, hy, bang_off, marks
        self.k_min = 0
        ax.set_facecolor("#111111")
        ax.set_xlim(center[0] - hx, center[0] + hx)
        ax.set_ylim(center[1] - hy, center[1] + hy)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#4a5c62")
            s.set_linewidth(1.2)
        if title:
            ax.set_title(title, color="white", fontsize=TITLE_FS, fontweight="bold", pad=14)
        f0 = frames[0]
        ext = (0, meta["gw"] * meta["food_cell"]) * 2
        self.food = ax.imshow(f0["food"], origin="lower", extent=ext, cmap=food_cmap, vmin=0.0, vmax=1.0,
                              interpolation="bilinear", zorder=0)
        for (cx, cy), cr in zip(meta["cov_c"], meta["cov_r"]):
            ax.add_patch(Circle((cx, cy), cr, facecolor="black", alpha=0.6, edgecolor=COVER_EDGE, linewidth=1.8,
                                zorder=1))
        self.night = ax.add_patch(Rectangle((center[0] - hx, center[1] - hy), 2 * hx, 2 * hy,
                                            facecolor="#000018", alpha=0.0, zorder=1.5, edgecolor="none"))
        self.trails = LineCollection([], linewidths=2.6, zorder=2, capstyle="round")
        ax.add_collection(self.trails)
        self.ptrails = LineCollection([], linewidths=3.0, zorder=2.2, capstyle="round")
        ax.add_collection(self.ptrails)
        self.stare = LineCollection([], linewidths=2.8 * lw_scale, zorder=3.5, capstyle="round")
        ax.add_collection(self.stare)
        e = np.zeros((0, 2))
        self.herb = ax.scatter(e[:, 0], e[:, 1], s=dot, zorder=4)
        self.bang = ax.scatter(e[:, 0], e[:, 1], marker="$!$", c="white", s=dot * 1.3, linewidths=0.6,
                               edgecolors="white", zorder=4.6)
        kw = dict(edgecolors="white", linewidths=1.8, zorder=5)
        self.chaser = ax.scatter(e[:, 0], e[:, 1], marker="X", c=CHASER_C, s=dot * 2.3, **kw)
        self.ranged = ax.scatter(e[:, 0], e[:, 1], marker="X", c=RANGED_C, s=dot * 2.3, **kw)
        self.stalker = ax.scatter(e[:, 0], e[:, 1], marker="X", c=STALKER_C, s=dot * 2.3, **kw)
        self.player = ax.scatter(e[:, 0], e[:, 1], marker="*", c=PLAYER_C, s=dot * 3.6, edgecolors="black",
                                 linewidths=1.0, zorder=5.5)
        self.sleepy = ax.scatter(e[:, 0], e[:, 1], marker="X", c="#777777", s=dot * 2.0, edgecolors="#bbbbbb",
                                 linewidths=1.0, zorder=5)
        self.catch_ring = ax.scatter(e[:, 0], e[:, 1], marker="o", facecolors="none", edgecolors="#ff2020",
                                     s=dot * 4.5, linewidths=3.2, zorder=6)
        self.lab_off = 1.7 * (1.0 if fs_scale >= 1.0 else 0.95)
        self.catch_txt = [ax.text(0, 0, "", color="#ff5050", fontsize=CATCH_FS * fs_scale, fontweight="bold", ha="center",
                                  va="top", zorder=7, clip_on=True) for _ in range(8)]
        # 노려보기 표시: 위협별 글자 하나('멈칫'·'물러남'·'들킴')와 물러남 점선 화살표
        M = len(f0["pred"])
        self.mark_txt = [ax.text(0, 0, "", color=MARK_C, fontsize=MARK_FS * fs_scale, fontweight="bold", ha="center",
                                 va="center", zorder=7, clip_on=True) for _ in range(M)]
        self.arrows = []
        for _ in range(M):
            a = ax.annotate("", xy=(0, 0), xytext=(0, 0), zorder=6.5, annotation_clip=True,
                            arrowprops=dict(arrowstyle="-|>,head_length=0.7,head_width=0.4", color=MARK_C, lw=2.4 * lw_scale,
                                            linestyle=(0, (3, 2)), shrinkA=0, shrinkB=0))
            a.set_visible(False)
            self.arrows.append(a)
        n = len(f0["pos"])
        self.last_done = np.full((len(frames), n), -10 ** 6, dtype=np.int64)
        cur = np.full(n, -10 ** 6, dtype=np.int64)
        for j, f in enumerate(frames):
            cur = np.where(f["done"], j, cur)
            self.last_done[j] = cur
        # 노려보기 선: 스텝 j 에 노려본(대치·들킴을 세는) 쌍. 끝난 뒤 STARE_HOLD 스텝 동안 옅어진다
        self.stare_last = np.full((len(frames), n), -10 ** 6, dtype=np.int64)
        self.stare_who = np.full((len(frames), n), -1, dtype=np.int64)
        cur, who = np.full(n, -10 ** 6, dtype=np.int64), np.full(n, -1, dtype=np.int64)
        for j, f in enumerate(frames):
            on = f["stare_by"] >= 0
            cur = np.where(on, j, cur)
            who = np.where(on, f["stare_by"], who)
            who = np.where(f["done"], -1, who)
            self.stare_last[j], self.stare_who[j] = cur, who

    def update(self, k, frac=0.0):
        from matplotlib.colors import to_rgba

        fr = self.frames
        f = fr[k]
        nxt = fr[k + 1] if (frac > 0 and k + 1 < len(fr)) else None
        g = nxt if nxt is not None else f          # 이산 상태(행동·위협 상태)는 다음 스텝 값 (원본과 같다)
        kk = k + 1 if nxt is not None else k
        pos = f["pos"].copy()
        pred = f["pred"].copy()
        beh, phase = g["beh"], g["phase"]
        if nxt is not None:
            ok = ~nxt["done"]
            pos[ok] = (1 - frac) * f["pos"][ok] + frac * nxt["pos"][ok]
            pred = (1 - frac) * f["pred"] + frac * nxt["pred"]
        self.food.set_data(f["food"])
        self.night.set_alpha(0.5 * f["dark"])
        age = k - self.last_done[k]
        alpha = np.clip(0.2 + 0.8 * age / FADE, 0.2, 1.0)
        m = in_win(pos, self.c, self.hx + 1, self.hy + 1)
        if HIDE_RESPAWNED:
            m &= self.last_done[k] < 1          # 이 갈래 안에서 한 번이라도 리스폰한 슬롯은 숨긴다
        bcol = np.array([to_rgba(c) for c in BEH_COLORS])
        cols = bcol[np.minimum(np.asarray(beh, dtype=np.int64), 3)].copy()
        cols[:, 3] = alpha
        crouch = (beh == 2) & (phase == 1)
        edge = np.where(crouch[:, None], np.array(to_rgba("#e8f0ff")), np.array((0, 0, 0, 1.0)))
        edge[:, 3] = alpha
        self.herb.set_offsets(pos[m] if m.any() else np.empty((0, 2)))
        self.herb.set_facecolor(cols[m])
        self.herb.set_edgecolor(edge[m])
        self.herb.set_linewidths(np.where(crouch[m], 2.6, 1.2))
        fz = m & (beh == 3)
        self.bang.set_offsets(pos[fz] + np.array([self.bang_off, 1.05 * self.bang_off]) if fz.any()
                              else np.empty((0, 2)))
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
                c = bcol[min(int(beh[s]), 3)]
                scol.append((c[0], c[1], c[2], 0.5 * alpha[s]))
        self.trails.set_segments(segs)
        if scol:
            self.trails.set_color(scol)
        pt, asl = f["ptype"], g["asleep"]
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
        # 노려보기 선 (노려보는 개체 → 포식자)
        ss, sc = [], []
        if self.marks:
            last, who = self.stare_last[kk], self.stare_who[kk]
            for s in np.flatnonzero((who >= 0) & (kk - last <= STARE_HOLD) & m):
                a = 1.0 if kk == last[s] else max(0.0, 1.0 - (kk - last[s] - (1 - frac if nxt is not None else 0))
                                                   / (STARE_HOLD + 1))
                p0, p1 = pos[s], pred[who[s]]
                v = p1 - p0
                n = np.linalg.norm(v)
                if n < 1e-6:
                    continue
                u = v / n
                ss.append(np.array([p0 + 0.55 * u, p1 - 0.9 * u]))
                sc.append((1.0, 0.95, 0.48, 0.9 * a))
        self.stare.set_segments(ss)
        if sc:
            self.stare.set_color(sc)
        # 위협 상태 글자·화살표
        for i in range(len(pred)):
            tx, ar = self.mark_txt[i], self.arrows[i]
            label, arrow = "", False
            if self.marks and in_win(pred[i], self.c, self.hx, self.hy)[0]:
                if pt[i] == W.PT_STALKER and not asl[i]:
                    if g["stalk"][i] == W.ST_STANDOFF:
                        label = "멈칫"
                    elif g["stalk"][i] == W.ST_BALK:
                        label, arrow = "물러남", True
                elif pt[i] == W.PT_PLAYER:
                    if g["pmode"][i] == W.PM_CHARGE:      # 돌진: 들킨 돌진은 걷기 속력까지만(못 뛴다)
                        label = "걷기만" if g["spotted_charge"][i] else "덮침"
                    elif g["spotted_left"][i] > 0:
                        label = "들킴"
            tx.set_text(label)
            if label:
                # 글자는 선·화살표·지나온 길과 겹치지 않게 그 방향에 수직인 쪽(위쪽 편)에 둔다
                if label == "멈칫" and g["lock"][i] >= 0:
                    d = pos[int(g["lock"][i])] - pred[i]
                elif label == "물러남":
                    d = np.asarray(g["balk_dir"][i], dtype=np.float64)
                else:
                    d = np.array([1.0, 0.0])
                n = np.linalg.norm(d)
                u = d / n if n > 1e-9 else np.array([1.0, 0.0])
                perp = np.array([-u[1], u[0]])
                if perp[1] < 0 or (abs(perp[1]) < 1e-9 and perp[0] < 0):
                    perp = -perp
                q = pred[i] + self.lab_off * perp
                tx.set_position((q[0], q[1]))
                tx.set_va("center")
            if arrow:
                d = np.asarray(g["balk_dir"][i], dtype=np.float64)
                n = np.linalg.norm(d)
                if n > 1e-9:
                    d = d / n
                    p0 = pred[i] + 1.0 * d
                    p1 = pred[i] + 3.6 * d
                    ar.xy = (float(p1[0]), float(p1[1]))
                    ar.set_position((float(p0[0]), float(p0[1])))
                    ar.set_visible(True)
                else:
                    ar.set_visible(False)
            else:
                ar.set_visible(False)
        cps = [fr[j]["caught"] for j in range(max(1, k - CATCH_SHOW + 1, self.k_min), k + 1) if len(fr[j]["caught"])]
        cps = np.concatenate(cps) if cps else np.empty((0, 2))
        cin = cps[in_win(cps, self.c, self.hx, self.hy)] if len(cps) else cps
        self.catch_ring.set_offsets(cin if len(cin) else np.empty((0, 2)))
        for j, tx in enumerate(self.catch_txt):
            if j < len(cin):
                tx.set_position((cin[j, 0], cin[j, 1] - 1.6))
                tx.set_text("잡힘")
            else:
                tx.set_text("")
        return self


def legend_handles(kind):
    from matplotlib.legend_handler import HandlerTuple
    from matplotlib.lines import Line2D

    dot = dict(marker="o", ls="none", markersize=20, markeredgecolor="black", markeredgewidth=1.2)
    h = [Line2D([], [], markerfacecolor=BEH_COLORS[0], **dot),
         Line2D([], [], markerfacecolor=BEH_COLORS[1], **dot),
         Line2D([], [], markerfacecolor=BEH_COLORS[2], **dot),
         (Line2D([], [], markerfacecolor=BEH_COLORS[3], **dot),
          Line2D([], [], marker="$!$", ls="none", markersize=20, color="white"))]
    labels = ["먹기", "도망", "숨기", "얼어붙기"]
    if kind == "player":
        h.append(Line2D([], [], marker="*", ls="none", markersize=30, markerfacecolor=PLAYER_C,
                        markeredgecolor="black", markeredgewidth=1.0))
        labels.append("플레이어")
    else:
        h.append(Line2D([], [], marker="X", ls="none", markersize=26, markerfacecolor=STALKER_C,
                        markeredgecolor="white", markeredgewidth=1.6))
        labels.append("몰래 다가오는 포식자")
    h.append(Line2D([], [], color=STARE_C, lw=2.6))
    labels.append("노려봄")
    return h, labels, {tuple: HandlerTuple(ndivide=None, pad=0.0)}


def make_figure(cache, kind):
    import matplotlib.pyplot as plt

    setup_font()
    pick, meta, branches = cache["pick"], cache["meta"], cache["branches"]
    fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI, facecolor=FIG_BG)
    panels = []
    for j, p in enumerate(POLS):
        ax = fig.add_axes(((ML + j * (PW + GAP)) / FIG_W, PY0 / FIG_H, PW / FIG_W, PH / FIG_H))
        panels.append(MapPanel(ax, meta, branches[p], pick["center"], TITLES[p]))
    h, labels, hmap = legend_handles(kind)
    fig.legend(handles=h, labels=labels, handler_map=hmap, loc="center left", ncol=len(h), fontsize=LEG_FS,
               frameon=False, labelcolor=FG, bbox_to_anchor=(ML / FIG_W, 0.5 * PY0 / FIG_H),
               handletextpad=0.4, columnspacing=1.6, handlelength=1.6)
    clk = fig.text((FIG_W - ML) / FIG_W, 0.5 * PY0 / FIG_H, "0:00", color=FG, fontsize=26, ha="right",
                   va="center", fontweight="bold")
    return fig, panels, clk


def draw_at(panels, clk, sec, step_sec, K):
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
    tag = args.tag or args.kind
    cache = load_cache(tag)
    fig, panels, clk = make_figure(cache, cache["kind"])
    for sec in args.secs:
        draw_at(panels, clk, sec, cache["step_sec"], cache["K"])
        out = CHECK / f"{tag}_t{sec:05.2f}.png"
        fig.savefig(str(out), dpi=args.dpi, facecolor=FIG_BG)
        print(out)
    plt.close(fig)


def cmd_render(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    from replay_v2 import _ffmpeg_exe, video_info

    tag = args.tag or args.kind
    cache = load_cache(tag)
    kind = cache["kind"]
    step_sec, K = cache["step_sec"], cache["K"]
    fig, panels, clk = make_figure(cache, kind)
    t1 = float(min(args.t1 if args.t1 is not None else K * step_sec, K * step_sec))
    t0 = float(args.t0)
    for pnl in panels:
        pnl.k_min = int(np.ceil(t0 / step_sec - 1e-9))
    poster_sec = args.poster
    draw_at(panels, clk, poster_sec, step_sec, K)
    name = args.name or f"{kind}_compare"
    png = OUT / f"{name}_poster.png"
    fig.savefig(str(png), dpi=DPI, facecolor=FIG_BG)
    n_run = int(round((t1 - t0) * FPS))
    secs = [t0] * args.hold0 + [min(t0 + i / FPS, t1) for i in range(n_run + 1)] + [t1] * args.hold1

    def upd(i):
        draw_at(panels, clk, secs[i], step_sec, K)
        return []

    matplotlib.rcParams["animation.ffmpeg_path"] = _ffmpeg_exe()
    writer = animation.FFMpegWriter(fps=FPS, codec="h264", bitrate=args.bitrate,
                                    extra_args=["-pix_fmt", "yuv420p", "-profile:v", "high", "-preset", "slow",
                                                "-movflags", "+faststart"])
    mp4 = OUT / f"{name}.mp4"
    tw = time.time()
    anim = animation.FuncAnimation(fig, upd, frames=len(secs), interval=1000 // FPS)
    anim.save(str(mp4), writer=writer, dpi=DPI, savefig_kwargs=dict(facecolor=FIG_BG))
    plt.close(fig)
    info = video_info(mp4)
    info["render_sec"] = round(time.time() - tw, 1)
    info.update(kind=kind, poster=str(png), poster_sec=poster_sec, speed=1.0, clip_clock_sec=[t0, t1],
                hold_start_sec=args.hold0 / FPS, hold_end_sec=args.hold1 / FPS, fps=FPS,
                window=dict(center=cache["pick"]["center"], half_x=HX, half_y=VIEW_HY),
                seed=cache["pick"]["seed"], t0_step=cache["pick"]["k0"], determinism=cache["det"],
                note="영상 시각 = 처음 멈춤 + (화면 시계 - 구간 시작). 화면 시계는 갈라진 순간부터의 게임 시간(실시간 1배).")
    (OUT / f"{name}_video.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False), flush=True)


def cmd_strip(args):
    """네 순간 띠: 위 = 노려보기 없음, 아래 = 노려보기 있음. 칸 위에 화면 시계, 칸 안 아래에 짧은 말."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    setup_font()
    tag = args.tag or args.kind
    cache = load_cache(tag)
    kind = cache["kind"]
    step_sec, K = cache["step_sec"], cache["K"]
    secs = args.secs
    caps = {"rbase": args.cap_left, "stare": args.cap_right}
    hx, hy = args.hx, args.hy
    c = list(args.center) if args.center else cache["pick"]["center"]
    cw, gap, ml, top = 4.6, 0.12, 1.45, 0.75
    chh = cw * hy / hx
    fw = ml + 4 * cw + 3 * gap + 0.15
    fh = top + 2 * chh + gap + 0.7
    fig = plt.figure(figsize=(fw, fh), dpi=150, facecolor=FIG_BG)
    for r, p in enumerate(POLS):
        y0 = fh - top - (r + 1) * chh - r * gap
        fig.text((ml - 0.18) / fw, (y0 + chh / 2) / fh, TITLES[p].replace(" ", chr(10)), color="white", fontsize=19,
                 fontweight="bold", ha="right", va="center", linespacing=1.3)
        for j, sec in enumerate(secs):
            ax = fig.add_axes(((ml + j * (cw + gap)) / fw, y0 / fh, cw / fw, chh / fh))
            pnl = MapPanel(ax, cache["meta"], cache["branches"][p], c, "", hx=hx, hy=hy, dot=args.dot,
                           bang_off=0.6, fs_scale=0.62, lw_scale=0.8)
            x = min(max(sec / step_sec, 0.0), float(K))
            k = int(np.floor(x + 1e-9))
            pnl.update(k, x - k)
            for col in ax.collections:
                if hasattr(col, "get_offsets") and len(col.get_offsets()) == 0:
                    col.set_visible(False)
            ax.text(0.03, 0.96, caps[p][j], transform=ax.transAxes, color="white", fontsize=16, fontweight="bold",
                    ha="left", va="top", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#000000", alpha=0.45, edgecolor="none"))
            if r == 0:
                fig.text((ml + j * (cw + gap) + cw / 2) / fw, (fh - top + 0.18) / fh, f"{sec:.1f}초",
                         color=FG, fontsize=18, fontweight="bold", ha="center", va="bottom")
    h, labels, hmap = legend_handles(kind)
    fig.legend(handles=h, labels=labels, handler_map=hmap, loc="center", ncol=len(h), fontsize=14,
               frameon=False, labelcolor=FG, bbox_to_anchor=(0.5, 0.3 / fh), handletextpad=0.4, columnspacing=1.4,
               markerscale=0.7)
    out = OUT / f"{args.name or kind + '_compare'}_strip.png"
    fig.savefig(str(out), dpi=150, facecolor=FIG_BG)
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--seeds", type=int, nargs=2, default=[31000, 31023])
    s.add_argument("--steps", type=int, default=SCAN_STEPS)
    s.add_argument("--workers", type=int, default=6)
    pr = sub.add_parser("probe")
    pr.add_argument("--kind", default="stalker", choices=("stalker", "player"))
    pr.add_argument("--top", type=int, default=24)
    pr.add_argument("--workers", type=int, default=6)
    sm = sub.add_parser("sim")
    sm.add_argument("--kind", default="stalker", choices=("stalker", "player"))
    sm.add_argument("--tag", help="캐시 이름(기본 = kind)")
    sm.add_argument("--rank", type=int, default=0)
    sm.add_argument("--extra", type=int, default=0, help="끝에 더 돌리는 스텝")
    sm.add_argument("--center", type=float, nargs=2)
    sm.add_argument("--shift", type=float, default=7.0, help="창 가운데: 표적 → 위협 쪽으로 옮기는 거리")
    sm.add_argument("--nudge", type=float, nargs=2, default=[0.0, 0.0], help="창 가운데에 더하는 (x, y)")
    st_ = sub.add_parser("stills")
    st_.add_argument("--kind", default="stalker", choices=("stalker", "player"))
    st_.add_argument("--tag", help="캐시 이름(기본 = kind)")
    st_.add_argument("--secs", type=float, nargs="+", default=[0.0, 2.5, 3.2, 4.0, 6.0])
    st_.add_argument("--dpi", type=int, default=60)
    r = sub.add_parser("render")
    r.add_argument("--kind", default="stalker", choices=("stalker", "player"))
    r.add_argument("--tag", help="캐시 이름(기본 = kind)")
    r.add_argument("--t0", type=float, default=0.0)
    r.add_argument("--t1", type=float)
    r.add_argument("--poster", type=float, default=3.4)
    r.add_argument("--hold0", type=int, default=HOLD0)
    r.add_argument("--hold1", type=int, default=HOLD1)
    r.add_argument("--bitrate", type=int, default=3600)
    r.add_argument("--name")
    sp = sub.add_parser("strip")
    sp.add_argument("--kind", default="stalker", choices=("stalker", "player"))
    sp.add_argument("--tag", help="캐시 이름(기본 = kind)")
    sp.add_argument("--secs", type=float, nargs=4, required=True)
    sp.add_argument("--cap-left", nargs=4, required=True, help="위 줄(노려보기 없음) 칸 말")
    sp.add_argument("--cap-right", nargs=4, required=True, help="아래 줄(노려보기 있음) 칸 말")
    sp.add_argument("--hx", type=float, default=12.0)
    sp.add_argument("--hy", type=float, default=10.0)
    sp.add_argument("--center", type=float, nargs=2)
    sp.add_argument("--dot", type=float, default=150)
    sp.add_argument("--name")
    args = ap.parse_args()
    {"scan": cmd_scan, "probe": cmd_probe, "sim": cmd_sim, "stills": cmd_stills, "render": cmd_render,
     "strip": cmd_strip}[args.cmd](args)
