"""같은 순간, 세 정책 — 반사실(counterfactual) 근접 장면 (R1b 시각 확인, 판정 아님).

사용자가 `results/v3/r1b/replay_rl_vs_fsm.mp4`(맵 전체, 12배속)를 보고 "RL이나 FSM이나 별 차이 안 보인다"고 했다.
이 스크립트는 같은 세계 상태에서 세 정책(RL 출시 모델 s3, FSM 손 규칙, R_base 손 규칙)을 갈라 돌려, 위협이 무리에
다가오는 순간을 실시간으로 확대해 나란히 보여 준다. 차이가 없으면 없는 대로 숫자로 적는다.

    python results/v3/r1b/visual/scenes.py search      # 평가 시드 10100~10119, RL 로 돌리며 후보 순간을 찾고 세 갈래로 잰다
    python results/v3/r1b/visual/scenes.py pick        # 미리 정한 규칙으로 장면 4개를 고른다 (select_rule 참고)
    python results/v3/r1b/visual/scenes.py render      # 고른 장면마다 mp4(RL | FSM | R_base) + PNG 띠

갈래 내기(branching): RL 로 세계를 돌리다 사건 t_e 의 LEAD(25)스텝 앞 t0 에서 `copy.deepcopy(World)` 를 세 벌 만들고,
각 벌에 새로 만든 정책을 `forward_bind` 로 붙여 K(150)스텝 돌린다. 같은 정책 두 벌이 비트 단위로 같은 궤적을 내는지
render 단계에서 장면마다 다시 확인한다(세계 난수 상태가 사본에 함께 들어간다는 증거).

주의(해석): 갈라진 순간(t0)에 이미 잠금 중인 행동(예: 얼기·숨기)은 RL 이 갈라지기 전에 고른 것이라 세 칸에 똑같이
나온다. 잠금이 끝나 첫 결정을 할 때까지는 FSM·R_base 칸도 RL 의 선택을 보여 준다. render 는 `rep_peek` 로 개체마다
첫 결정 시점을 기록해 이 '물려받은' 스텝을 따로 센다(`branch_summary.share_own` 은 뺀 값). 또 갈라진 뒤에는 위치·위협·
이웃도 달라지므로, 몇 초 뒤의 차이는 '두뇌의 선택'과 '달라진 상황'이 섞인 것이다.

영상 자막 숫자는 손으로 적지 않는다: `scene_stats` 가 기록된 프레임(패널 왼쪽 위 숫자와 같은 규칙: 확대 창 안, 보간 없는
스텝)에서 세고, `make_caption` 이 그 값으로 자막을 만든다. 같은 값이 scenes.json(`caption`, `caption_numbers`)과
captions.json 에 함께 쓰인다.

이 파일은 저장소의 다른 파일을 고치지 않는다. 포획 개체를 알려고 `World._step_predators_v3` 를 이 프로세스 안에서만 감싼다
(반환값을 `_sc_caught` 에 복사할 뿐 동역학은 같다).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                      # herbivore_rl/
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import numpy as np  # noqa: E402

from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import build_policy, forward_bind, forward_done  # noqa: E402
from env_v2 import world as W  # noqa: E402

CONFIG = "configs/v3_r1_on.yaml"
SEEDS = list(range(10100, 10120))
STEPS = 3000            # 시드마다 RL 본 궤적 길이 (400초)
LEAD = 25               # 사건 몇 스텝 앞에서 가르나 (3.3초)
K = 150                 # 갈래 길이 (20초)
GAP = 30                # 사건 '시작' 판단: 직전 GAP 스텝 동안 조건이 없었다
OUT = HERE / "scenes"

SPECS = {
    "rl": {"kind": "rep_learned", "path": "ckpt/v3/v3_r1_g995_s3_20m.zip"},
    "fsm": json.loads((ROOT / "results/v3/r1b/fsm_spec.json").read_text(encoding="utf-8")),
    "rbase": json.loads((ROOT / "results/v3/r1b/rbase_spec.json").read_text(encoding="utf-8")),
}
POLS = ("rl", "fsm", "rbase")

_orig_sp = W.World._step_predators_v3


def _sp_rec(self):
    caught = _orig_sp(self)
    self._sc_caught = caught.copy()
    return caught


W.World._step_predators_v3 = _sp_rec


def load_cfg():
    return load_v2_config(ROOT / CONFIG)


def new_world(cfg, seed):
    return W.World(cfg, seeds=[seed])


def bound_policy(name, world, seed):
    p = build_policy(SPECS[name], seed)
    forward_bind(p, world)
    return p


def step(world, pol):
    a = pol(world.observe())
    _, _, done, _ = world.step(a)
    forward_done(pol, done)
    return done


def active_threats(w) -> np.ndarray:
    """지금 사냥할 수 있는 위협: 깨어 있고, 먹은 뒤 쉬는 중이 아니고, 탈진·휴식이 아니다."""
    act = w.pred_cd == 0
    if getattr(w, "pred_asleep", None) is not None:
        act &= ~w.pred_asleep
    st = w.pred_type == W.PT_STALKER
    act &= ~(st & (w.stalk_state == W.ST_EXHAUST))
    act &= ~(w.pred_is_player & (w.player_mode == W.PM_REST))
    return act


def dists(w) -> np.ndarray:
    d = w.pred_pos[:, None, :] - w.pos[None, :, :]
    return np.sqrt((d ** 2).sum(-1))                    # (M, N)


# --------------------------------------------------------------------- #
# 갈래 (지표만)
# --------------------------------------------------------------------- #


def branch_metrics(snap, name, seed, focus, k_steps=K):
    w = copy.deepcopy(snap)
    pol = bound_policy(name, w, seed)
    nf = len(focus)
    beh = np.zeros((k_steps, nf), dtype=np.int8)
    alive = np.ones((k_steps, nf), dtype=bool)
    live = np.ones(nf, dtype=bool)
    caught_f = 0
    caught_all = 0
    for k in range(k_steps):
        done = step(w, pol)
        alive[k] = live
        beh[k] = w.behavior[focus]
        c = w._sc_caught
        caught_f += int((c[focus] & live).sum())
        caught_all += int(c.sum())
        live &= ~done[focus]
    return dict(beh=beh, alive=alive, caught_f=caught_f, caught_all=caught_all, pos_end=w.pos[focus].copy(),
                live_end=live)


def disagree(a, b) -> float:
    m = a["alive"] & b["alive"]
    return float((a["beh"][m] != b["beh"][m]).mean()) if m.any() else 0.0


def hist(a) -> list:
    v = a["beh"][a["alive"]].astype(np.int64)
    h = np.bincount(v, minlength=5)[:4] / max(len(v), 1)
    return [round(float(x), 4) for x in h]


# --------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------- #


def search_seed(seed):
    cfg = load_cfg()
    w = new_world(cfg, seed)
    pol = bound_policy("rl", w, seed)
    ring = deque(maxlen=LEAD + 1)
    hist_n6 = deque(maxlen=GAP)
    hist_nc = deque(maxlen=GAP)
    events, last = [], []
    t_start = time.time()
    for t in range(STEPS):
        ring.append(copy.deepcopy(w))
        d = dists(w)
        act = active_threats(w)
        n6 = ((d <= 6.0).sum(1)) * act
        n8 = ((d <= 8.0).sum(1)) * act
        incov = w._in_cover(w.pos)
        nc = (((d <= 8.0) & incov[None, :]).sum(1)) * act
        st0, pm0 = w.stalk_state.copy(), w.player_mode.copy()
        pp = w.pred_pos.copy()
        step(w, pol)
        pounce = (st0 == W.ST_ROAM) & (w.stalk_state == W.ST_POUNCE)
        charge = (pm0 != W.PM_CHARGE) & (w.player_mode == W.PM_CHARGE)
        prev6 = np.max(np.stack(hist_n6), 0) if hist_n6 else np.zeros_like(n6)
        prevc = np.max(np.stack(hist_nc), 0) if hist_nc else np.zeros_like(nc)
        hist_n6.append(n6)
        hist_nc.append(nc)
        if t < LEAD or len(ring) < LEAD + 1:
            continue
        for i in range(w.M):
            kind = None
            if pounce[i] and n8[i] >= 3:
                kind = "pounce"
            elif charge[i] and n8[i] >= 3:
                kind = "charge"
            elif w.pred_type[i] == W.PT_CHASER and n6[i] >= 3 and prev6[i] < 3:
                kind = "chase"
            elif nc[i] >= 2 and prevc[i] < 2:
                kind = "cover"
            if kind is None:
                continue
            if any(t - tl < 60 and np.linalg.norm(pp[i] - pl) < 12.0 for tl, pl in last):
                continue
            last.append((t, pp[i].copy()))
            snap = ring[0]
            assert snap.t == t - LEAD
            d0 = np.linalg.norm(snap.pos - snap.pred_pos[i], axis=1)
            focus = np.flatnonzero((d0 <= 12.0) | (d[i] <= 8.0))
            if len(focus) < 3:
                continue
            events.append(dict(seed=seed, t_e=t, t0=t - LEAD, threat=int(i), kind=kind,
                               ptype=int(w.pred_type[i]), n8=int(n8[i]), ncov=int(nc[i]),
                               focus=focus.tolist(), snap=snap))
    t_main = time.time() - t_start
    out = []
    for ev in events:
        snap = ev.pop("snap")
        br = {p: branch_metrics(snap, p, seed, np.asarray(ev["focus"])) for p in POLS}
        ev["metrics"] = dict(
            d_rl_fsm=disagree(br["rl"], br["fsm"]), d_rl_rbase=disagree(br["rl"], br["rbase"]),
            d_fsm_rbase=disagree(br["fsm"], br["rbase"]),
            hist={p: hist(br[p]) for p in POLS},
            nongraze={p: round(1.0 - hist(br[p])[0], 4) for p in POLS},
            caught_focus={p: br[p]["caught_f"] for p in POLS},
            caught_all={p: br[p]["caught_all"] for p in POLS},
            pos_div_rl_fsm=float(np.linalg.norm(br["rl"]["pos_end"] - br["fsm"]["pos_end"], axis=1)[
                br["rl"]["live_end"] & br["fsm"]["live_end"]].mean()) if (br["rl"]["live_end"] & br["fsm"]["live_end"]).any() else None,
        )
        m = ev["metrics"]
        m["score"] = 0.5 * (m["d_rl_fsm"] + m["d_rl_rbase"])
        out.append(ev)
    print(f"seed {seed}: {len(out)} 후보, 본 궤적 {t_main:.0f}초, 전체 {time.time() - t_start:.0f}초", flush=True)
    return out


def cmd_search(args):
    from concurrent.futures import ProcessPoolExecutor

    seeds = SEEDS if not args.seeds else [int(s) for s in args.seeds]
    res = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(search_seed, seeds):
            res.extend(r)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "candidates.json").write_text(json.dumps(dict(
        config=CONFIG, seeds=seeds, steps=STEPS, lead=LEAD, k=K, gap=GAP, specs=SPECS, candidates=res),
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"후보 {len(res)}개 -> {OUT / 'candidates.json'}")


# --------------------------------------------------------------------- #
# pick
# --------------------------------------------------------------------- #

SELECT_RULE = (
    "후보 = 평가 시드 10100~10119 를 RL 로 3000스텝 돌리며 찾은 순간: 잠행형 돌진 시작·플레이어 돌진 시작(위협 8 안 초식 ≥ 3), "
    "추격형이 초식 3마리 이상의 6 안으로 처음 들어옴, 은신처 안 초식 2마리 이상의 8 안으로 처음 들어옴(직전 30스텝에 없던 조건). "
    "같은 곳(12 안)·60스텝 안 중복은 뺀다. 초점 개체 = t0 에 위협 12 안 또는 t_e 에 8 안. 점수 = 초점 개체-스텝 중 행동이 다른 비율을 "
    "RL-FSM, RL-R_base 로 평균. 장면 1 = 점수 최대. 장면 2 = RL 자신의 먹기 외 행동 비율 ≥ 10% 인 후보 중 점수 최대(다른 시드). "
    "장면 3 = 초점 개체 포획 수 차이 |RL−FSM|+|RL−R_base| 최대(동점이면 점수, 다른 시드). 장면 4 = 점수가 전체 중앙값에 가장 가까운 후보"
    "(다른 시드, '보통' 장면). 이 규칙은 전체 후보 분포를 보기 전에 정했다(코드 시험으로 돌린 시드 10100 의 후보 목록만 봤다)."
)


def cmd_pick(args):
    data = json.loads((OUT / "candidates.json").read_text(encoding="utf-8"))
    C = data["candidates"]
    sc = np.array([c["metrics"]["score"] for c in C])
    used = set()

    def best(pool, key):
        pool = [c for c in pool if c["seed"] not in used]
        if not pool:
            return None
        c = max(pool, key=key)
        used.add(c["seed"])
        return c

    s1 = best(C, lambda c: c["metrics"]["score"])
    s2 = best([c for c in C if c["metrics"]["nongraze"]["rl"] >= 0.10], lambda c: c["metrics"]["score"])

    def cdiff(c):
        cf = c["metrics"]["caught_focus"]
        return abs(cf["rl"] - cf["fsm"]) + abs(cf["rl"] - cf["rbase"])

    s3 = best(C, lambda c: (cdiff(c), c["metrics"]["score"]))
    med = float(np.median(sc))
    s4 = best(C, lambda c: -abs(c["metrics"]["score"] - med))
    picks = []
    for tag, c in (("최대 차이", s1), ("RL 이 먹기 말고 다른 행동을 하는 장면", s2), ("포획 결과가 다른 장면", s3),
                   ("보통 장면(점수 중앙값)", s4)):
        if c is not None:
            picks.append(dict(tag=tag, **{k: c[k] for k in ("seed", "t_e", "t0", "threat", "kind", "ptype", "focus")},
                              metrics=c["metrics"]))
    q = lambda a: [round(float(x), 4) for x in np.quantile(a, [0.1, 0.25, 0.5, 0.75, 0.9])]  # noqa: E731
    drf = np.array([c["metrics"]["d_rl_fsm"] for c in C])
    drb = np.array([c["metrics"]["d_rl_rbase"] for c in C])
    dfb = np.array([c["metrics"]["d_fsm_rbase"] for c in C])
    ng = {p: np.array([c["metrics"]["nongraze"][p] for c in C]) for p in POLS}
    cf = {p: np.array([c["metrics"]["caught_focus"][p] for c in C]) for p in POLS}
    kinds = {}
    for c in C:
        kinds.setdefault(c["kind"], []).append(c)
    summary = dict(
        n_candidates=len(C), rule=SELECT_RULE,
        quantiles_10_25_50_75_90=dict(score=q(sc), d_rl_fsm=q(drf), d_rl_rbase=q(drb), d_fsm_rbase=q(dfb)),
        frac_d_rl_fsm_below=dict(**{f"<{x}": round(float((drf < x).mean()), 4) for x in (0.02, 0.05, 0.10, 0.20)}),
        frac_d_rl_rbase_below=dict(**{f"<{x}": round(float((drb < x).mean()), 4) for x in (0.02, 0.05, 0.10, 0.20)}),
        mean_nongraze={p: round(float(ng[p].mean()), 4) for p in POLS},
        frac_rl_all_graze=round(float((ng["rl"] < 0.005).mean()), 4),
        frac_fsm_all_graze=round(float((ng["fsm"] < 0.005).mean()), 4),
        mean_caught_focus={p: round(float(cf[p].mean()), 4) for p in POLS},
        total_caught_focus={p: int(cf[p].sum()) for p in POLS},
        frac_caught_differs_rl_fsm=round(float((cf["rl"] != cf["fsm"]).mean()), 4),
        by_kind={k: dict(n=len(v), median_d_rl_fsm=round(float(np.median([c["metrics"]["d_rl_fsm"] for c in v])), 4),
                         median_d_rl_rbase=round(float(np.median([c["metrics"]["d_rl_rbase"] for c in v])), 4),
                         mean_nongraze={p: round(float(np.mean([c["metrics"]["nongraze"][p] for c in v])), 4)
                                        for p in POLS})
                 for k, v in kinds.items()},
    )
    (OUT / "select.json").write_text(json.dumps(dict(summary=summary, picks=picks), ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for p in picks:
        m = p["metrics"]
        print(p["tag"], p["seed"], p["t_e"], p["kind"], "score", round(m["score"], 3), "dRF", round(m["d_rl_fsm"], 3),
              "dRB", round(m["d_rl_rbase"], 3), "ng", m["nongraze"], "caught", m["caught_focus"])


# --------------------------------------------------------------------- #
# render: 장면마다 세 갈래를 프레임으로 남기고 mp4(RL | FSM | R_base) + PNG 띠
# --------------------------------------------------------------------- #

HALF = 16.0             # 확대 창 반폭 (32 × 32 세계 단위)
SUB = 2                 # 스텝당 영상 프레임 (7.5스텝/초 × 2 = 15fps → 실시간 1배속)
FPS = 15
HOLD0, HOLD1 = 30, 22   # 첫·끝 화면 멈춤(프레임)
TRAIL = 12              # 초식 꼬리 (스텝)
PTRAIL = 24             # 위협 꼬리 (스텝)
CATCH_SHOW = 14         # 잡힘 표시 유지 (스텝)
FADE = 8                # 리스폰 직후 흐림 (스텝)
TITLES = {"rl": "RL 학습 정책 (출시 모델 s3)", "fsm": "FSM 손 규칙 (숨기 > 얼기 > 먹기)",
          "rbase": "R_base 손 규칙 (먹다가 가까우면 도망)"}
KIND_KO = {"pounce": "잠행형 포식자가 돌진을 시작", "charge": "플레이어형 위협이 돌진을 시작",
           "chase": "추격형 포식자가 무리 6 안으로 들어옴", "cover": "위협이 은신처 안 개체들 8 안으로 들어옴"}
BEH_KO = ("먹기", "도망", "숨기", "얼기")


def _frame(w, caught_pos):
    return dict(pos=w.pos.copy(), head=w.head.copy(), beh=w.behavior.astype(np.int8).copy(),
                phase=w.beh_phase.astype(np.int8).copy(), pred=w.pred_pos.copy(), ptype=w.pred_type.copy(),
                ranged=w.pred_ranged.copy(), stalk=w.stalk_state.copy(), pmode=w.player_mode.copy(),
                asleep=(w.pred_asleep.copy() if getattr(w, "pred_asleep", None) is not None
                        else np.zeros(w.M, dtype=bool)),
                food=w.food.copy(), dark=float(np.mean(w.dark)), caught=caught_pos, t=int(w.t),
                incov=w._in_cover(w.pos))


def record_branch(snap, name, seed, k_steps=K):
    """한 갈래를 K 스텝 돌리며 프레임을 남긴다. `reads` = 그 스텝이 결정 시점인 개체(`rep_peek`, 순수 함수 — 궤적을
    바꾸지 않는다. render 의 '원래 궤적과 같음' 확인이 이를 검사한다)."""
    w = copy.deepcopy(snap)
    pol = bound_policy(name, w, seed)
    frames = [_frame(w, np.empty((0, 2)))]
    frames[0]["done"] = np.zeros(w.N, dtype=bool)
    frames[0]["caught_slots"] = np.empty(0, dtype=np.int64)
    frames[0]["reads"] = np.zeros(w.N, dtype=bool)
    for _ in range(k_steps):
        pre = w.pos.copy()
        reads = np.asarray(w.rep_peek()["reads"], dtype=bool).copy()
        done = step(w, pol)
        c = w._sc_caught
        f = _frame(w, pre[c])
        f["done"] = done.copy()
        f["caught_slots"] = np.flatnonzero(c)
        f["reads"] = reads
        frames.append(f)
    return frames, w


def inherited_mask(frames) -> np.ndarray:
    """(K+1, N) — 그 프레임의 행동이 아직 갈라지기 전(RL)의 선택인 개체 슬롯: 갈라진 뒤 결정 시점(reads)도, 죽음도 아직
    없었다. 잠금 중이라 요청을 읽지 않으므로 행동은 t0 의 것 그대로다."""
    inh = np.ones(len(frames[0]["beh"]), dtype=bool)
    out = [inh.copy()]
    for f in frames[1:]:
        inh &= ~f["reads"] & ~f["done"]        # 죽은 슬롯은 새 개체(먹기로 시작)
        out.append(inh.copy())
    return np.asarray(out)


def traj_key(frames):
    return [np.concatenate([f["pos"].ravel(), f["pred"].ravel(), f["beh"].astype(np.float64), f["food"].ravel()])
            for f in frames]


def same_traj(a, b) -> bool:
    return len(a) == len(b) and all(np.array_equal(x, y) for x, y in zip(traj_key(a), traj_key(b)))


def window_of(frames_rl, pick, size):
    i = pick["threat"]
    focus = np.asarray(pick["focus"])
    f0, fe = frames_rl[0], frames_rl[LEAD]
    pts = np.stack([f0["pred"][i], fe["pred"][i], f0["pos"][focus].mean(0), fe["pos"][focus].mean(0)])
    c = pts.mean(0)
    c = np.clip(c, HALF, max(size - HALF, HALF))
    return [float(c[0]), float(c[1])]


def in_win(p, c):
    p = np.asarray(p).reshape(-1, 2)
    return (np.abs(p[:, 0] - c[0]) <= HALF) & (np.abs(p[:, 1] - c[1]) <= HALF)


def branch_summary(frames, focus, c):
    """초점 개체(원래 개체가 살아 있는 동안)의 행동 비율, 첫 반응, 포획.
    share_all 은 갈라지기 전 RL 이 고른 잠금(물려받은 스텝)을 포함하고, share_own 은 뺀다(그 갈래 정책이 직접 고른 것만)."""
    focus = np.asarray(focus)
    inh = inherited_mask(frames)[:, focus]
    live = np.ones(len(focus), dtype=bool)
    cnt = np.zeros(4)
    cnt_own = np.zeros(4)
    n_inh_nongraze = 0
    first = None
    caught = 0
    for k, f in enumerate(frames[1:], start=1):
        b = f["beh"][focus]
        for j in range(4):
            cnt[j] += np.sum(live & (b == j))
            cnt_own[j] += np.sum(live & ~inh[k] & (b == j))
        n_inh_nongraze += int(np.sum(live & inh[k] & (b != 0)))
        if first is None and np.any(live & (b != 0)):
            first = k
        caught += int(np.sum(live & np.isin(focus, f["caught_slots"])))
        live &= ~f["done"][focus]
    share = cnt / max(cnt.sum(), 1)
    share_own = cnt_own / max(cnt_own.sum(), 1)
    catches_win = sum(int(np.sum(in_win(f["caught"], c))) for f in frames[1:] if len(f["caught"]))
    # 사건 앞뒤 창(사건 −5 ~ +60 스텝)의 행동 비율 (초점 개체)
    live = np.ones(len(focus), dtype=bool)
    cnt2 = np.zeros(4)
    for k, f in enumerate(frames[1:], start=1):
        if LEAD - 5 <= k <= LEAD + 60:
            b = f["beh"][focus]
            for j in range(4):
                cnt2[j] += np.sum(live & (b == j))
        live &= ~f["done"][focus]
    share2 = cnt2 / max(cnt2.sum(), 1)
    return dict(share_all={BEH_KO[j]: round(float(share[j]), 3) for j in range(4)},
                share_own={BEH_KO[j]: round(float(share_own[j]), 3) for j in range(4)},
                inherited_nongraze_share_of_all=round(float(n_inh_nongraze / max(cnt.sum(), 1)), 3),
                share_event={BEH_KO[j]: round(float(share2[j]), 3) for j in range(4)},
                first_nongraze_sec=None if first is None else round(first * 8 / 60.0, 2),
                caught_focus=caught, caught_in_window=catches_win)


# --------------------------------------------------------------------- #
# 자막 숫자: 기록된 프레임에서 센다 (패널 왼쪽 위 숫자와 같은 규칙)
# --------------------------------------------------------------------- #

EARLY = 15              # 사건 뒤 '처음 2초' (15스텝 = 2.0초)
LAB = {"rl": "RL", "fsm": "FSM", "rbase": "R_base"}
BEH_COLOR_KO = ("초록", "주황", "파랑", "흰색 !")


def screen_counts(frames, c) -> np.ndarray:
    """(K+1, 4) 프레임(스텝 k, 보간 없음)마다 확대 창 안 행동 수 — 패널 왼쪽 위 '먹기 · 도망 · 숨기 · 얼기' 숫자와 같다."""
    return np.array([np.bincount(f["beh"][in_win(f["pos"], c)].astype(np.int64), minlength=5)[:4] for f in frames])


def _alive(frames, focus) -> np.ndarray:
    """(K+1, F) 원래 개체가 아직 살아 있나(그 프레임까지 죽음 없음)."""
    live = np.ones(len(focus), dtype=bool)
    out = [live.copy()]
    for f in frames[1:]:
        live &= ~f["done"][focus]
        out.append(live.copy())
    return np.asarray(out)


def scene_stats(pick, branches, step_sec, moments) -> dict:
    c = pick["center"]
    focus = np.asarray(pick["focus"])
    cnt = {p: screen_counts(branches[p], c) for p in POLS}
    for p in POLS:                                        # 갈라진 순간은 세 칸이 같아야 한다
        assert np.array_equal(cnt[p][0], cnt["rl"][0]), (p, cnt[p][0], cnt["rl"][0])
    after = slice(LEAD + 1, K + 1)                        # 사건 다음 스텝부터 끝까지
    rng = {p: {BEH_KO[j]: [int(cnt[p][after, j].min()), int(cnt[p][after, j].max())] for j in range(4)} for p in POLS}
    mean_after = {p: {BEH_KO[j]: round(float(cnt[p][after, j].mean()), 2) for j in range(4)} for p in POLS}
    caught_win = {p: int(sum(int(np.sum(in_win(f["caught"], c))) for f in branches[p][1:] if len(f["caught"])))
                  for p in POLS}
    # 갈라지기 전에 RL 이 고른 행동(물려받음) — 화면 안, 먹기 아님
    inh_last_k, inh_event = {}, {}
    for p in POLS:
        fr = branches[p]
        inh = inherited_mask(fr)
        ng0 = fr[0]["beh"] != 0
        last = 0
        for k, f in enumerate(fr):
            if np.any(inh[k] & ng0 & in_win(f["pos"], c)):
                last = k
        inh_last_k[p] = last
        inh_event[p] = int(np.sum(inh[LEAD] & ng0 & in_win(fr[LEAD]["pos"], c)))
    # 같은 개체 불일치·위치 차이 (초점 개체, 두 갈래 모두 원래 개체가 살아 있는 동안)
    alive = {p: _alive(branches[p], focus) for p in POLS}

    def dis(a, b, ks):
        n = d = 0
        for k in ks:
            m = alive[a][k] & alive[b][k]
            n += int(m.sum())
            d += int(np.sum(m & (branches[a][k]["beh"][focus] != branches[b][k]["beh"][focus])))
        return round(d / n, 4) if n else None

    def gap(a, b, k):
        m = alive[a][k] & alive[b][k]
        if not m.any():
            return None
        return round(float(np.linalg.norm(branches[a][k]["pos"][focus][m] - branches[b][k]["pos"][focus][m],
                                          axis=1).mean()), 2)

    early = range(LEAD + 1, LEAD + 1 + EARLY)
    return dict(
        rule="확대 창(±16) 안, 스텝 k 의 프레임(보간 없음) — 패널 왼쪽 위 숫자와 같다. '사건 뒤' = 사건 다음 스텝 ~ 끝",
        on_screen_at_split=int(cnt["rl"][0].sum()),
        at_split_counts={BEH_KO[j]: int(cnt["rl"][0][j]) for j in range(4)},
        after_event_range=rng, after_event_mean=mean_after,
        moment_counts={p: [{"sec": round(k * step_sec, 1), **{BEH_KO[j]: int(cnt[p][k][j]) for j in range(4)}}
                           for k in moments] for p in POLS},
        caught_in_window=caught_win,
        inherited_on_screen_until_sec={p: round(inh_last_k[p] * step_sec, 1) for p in POLS},
        inherited_on_screen_at_event=inh_event,
        disagree_first_2s_after_event={"rl_fsm": dis("rl", "fsm", early), "rl_rbase": dis("rl", "rbase", early)},
        disagree_whole_branch={"rl_fsm": dis("rl", "fsm", range(1, K + 1)),
                               "rl_rbase": dis("rl", "rbase", range(1, K + 1))},
        pos_gap_focus={"rl_fsm": {"event": gap("rl", "fsm", LEAD), "end": gap("rl", "fsm", K)},
                       "rl_rbase": {"event": gap("rl", "rbase", LEAD), "end": gap("rl", "rbase", K)}},
    )


INTRO = {
    "최대 차이": "차이가 가장 큰 장면({n}개 순간 중 1위)",
    "RL 이 먹기 말고 다른 행동을 하는 장면": "RL이 먹기 말고 다른 행동을 많이 하는 장면(그런 순간 중 장면 1과 다른 시드에서 "
                                             "차이 1위)",
    "포획 결과가 다른 장면": "잡힌 수가 가장 크게 갈린 장면({n}개 순간 중 1위)",
    "보통 장면(점수 중앙값)": "'보통' 장면(차이 점수가 {n}개 순간의 한가운데에 가장 가까움)",
}


def _pct0(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def make_caption(pick, st, step_sec, n_cand) -> tuple[str, dict]:
    """자막(5줄)과 거기 쓴 숫자. 숫자는 모두 `scene_stats` 값이다."""
    t_ev = LEAD * step_sec
    intro = INTRO.get(pick["tag"], pick["tag"]).format(n=n_cand)
    l1 = (f"{intro}. +{t_ev:.1f}초에 {KIND_KO[pick['kind']]}(RL 갈래 기준). "
          f"갈라진 순간 화면 안 {st['on_screen_at_split']}마리.")
    parts = []
    for p in POLS:
        r, mu = st["after_event_range"][p], st["after_event_mean"][p]
        js = sorted((j for j in (1, 2, 3) if r[BEH_KO[j]][1] > 0), key=lambda j: -mu[BEH_KO[j]])
        desc = "·".join(f"{BEH_KO[j]} {r[BEH_KO[j]][0]}~{r[BEH_KO[j]][1]}" for j in js) or "모두 먹기"
        parts.append(f"{LAB[p]} {desc}")
    l2 = "사건 뒤 화면 안 먹기 아닌 점(적을 때~많을 때, 주황 도망·파랑 숨기·흰색 얼기): " + " | ".join(parts)
    a0 = st["at_split_counts"]
    inh = [f"{BEH_KO[j]} {a0[BEH_KO[j]]}({BEH_COLOR_KO[j]})" for j in (1, 2, 3) if a0[BEH_KO[j]] > 0]
    if inh:
        until = max(st["inherited_on_screen_until_sec"].values())
        l3 = (f"갈라진 순간 보이는 {'·'.join(inh)}은 세 칸 모두 같다 — RL이 갈라지기 전에 고른 행동이라 RL만의 것이 아니다"
              f"(길게는 +{until:.1f}초까지 세 칸에 남는다).")
    else:
        l3 = "갈라진 순간에는 화면 안이 모두 먹기다(세 칸 같음). 그 뒤의 먹기 아닌 행동은 각 칸 정책이 고른 것이다."
    pg = st["pos_gap_focus"]["rl_fsm"]["end"]
    de = st["disagree_first_2s_after_event"]
    l4 = (f"갈라진 뒤엔 위치도 달라져(끝에 같은 개체의 RL–FSM 거리 평균 {pg:.1f}칸) 뒤쪽 차이가 모두 두뇌의 선택 탓은 아니다. "
          f"사건 뒤 2초간 같은 개체의 행동이 다른 비율: RL–FSM {_pct0(de['rl_fsm'])}, RL–R_base {_pct0(de['rl_rbase'])}.")
    cw = st["caught_in_window"]
    l5 = (f"20초 동안 이 화면 안에서 잡힌 수: RL {cw['rl']} · FSM {cw['fsm']} · R_base {cw['rbase']} "
          f"(한 장면의 잡힌 수는 우연이 크다. {n_cand}개 순간 평균은 셋이 거의 같다).")
    nums = dict(on_screen_at_split=st["on_screen_at_split"], at_split_counts=a0,
                after_event_range=st["after_event_range"],
                inherited_on_screen_until_sec=st["inherited_on_screen_until_sec"],
                pos_gap_rl_fsm_end=pg, disagree_first_2s_after_event=de, caught_in_window=cw)
    return "\n".join([l1, l2, l3, l4, l5]), nums


class MapPanel:
    """확대 창 하나 (세 갈래 중 하나)."""

    def __init__(self, ax, world, frames, center, title, small=False):
        from matplotlib.collections import LineCollection
        from matplotlib.patches import Circle, Rectangle
        from replay_v2 import BG, FOOD_CMAP

        self.ax, self.frames, self.c, self.small = ax, frames, center, small
        cfg = world.cfg
        ax.set_facecolor(BG)
        ax.set_xlim(center[0] - HALF, center[0] + HALF)
        ax.set_ylim(center[1] - HALF, center[1] + HALF)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#666666")
        if title:
            ax.set_title(title, color="white", fontsize=13 if not small else 10, pad=5)
        f0 = frames[0]
        ext = (0, world.gw * cfg.food_cell) * 2
        self.food = ax.imshow(f0["food"], origin="lower", extent=ext, cmap=FOOD_CMAP, vmin=0.0, vmax=1.0,
                              interpolation="bilinear", zorder=0)
        for (cx, cy), cr in zip(world.cov_c, world.cov_r):
            ax.add_patch(Circle((cx, cy), cr, facecolor="black", alpha=0.55, edgecolor="#7f8fd0", linewidth=1.2,
                                zorder=1))
        self.night = ax.add_patch(Rectangle((center[0] - HALF, center[1] - HALF), 2 * HALF, 2 * HALF,
                                            facecolor="#000018", alpha=0.0, zorder=1.5, edgecolor="none"))
        self.trails = LineCollection([], linewidths=1.2, zorder=2)
        ax.add_collection(self.trails)
        self.ptrails = LineCollection([], linewidths=1.6, zorder=2.2)
        ax.add_collection(self.ptrails)
        dot = 40 if small else 95
        self.dot = dot
        self.arrows = ax.quiver(np.zeros(1), np.zeros(1), np.zeros(1), np.zeros(1), angles="xy", scale_units="xy",
                                scale=1.0, width=0.004, headwidth=3.0, headlength=3.5, headaxislength=3.0,
                                color="white", zorder=3)
        self.herb = ax.scatter(np.zeros(0), np.zeros(0), s=dot, zorder=4)
        self.bang = ax.scatter(np.zeros(0), np.zeros(0), marker="$!$", c="white", s=dot * 1.4, zorder=4.6)
        kw = dict(edgecolors="white", linewidths=1.0, zorder=5)
        self.chaser = ax.scatter(np.zeros(0), np.zeros(0), marker="X", c="#ff2d2d", s=dot * 2.6, **kw)
        self.ranged = ax.scatter(np.zeros(0), np.zeros(0), marker="x", c="#ff7a7a", s=dot * 2.0, linewidths=2.4,
                                 zorder=5)
        self.stalker = ax.scatter(np.zeros(0), np.zeros(0), marker="X", c="#ffb020", s=dot * 2.6, **kw)
        self.player = ax.scatter(np.zeros(0), np.zeros(0), marker="*", c="#00e5ff", s=dot * 4.2, edgecolors="black",
                                 linewidths=0.9, zorder=5.5)
        self.sleepy = ax.scatter(np.zeros(0), np.zeros(0), marker="X", c="#777777", s=dot * 2.2,
                                 edgecolors="#bbbbbb", linewidths=0.8, zorder=5)
        self.dash_ring = ax.scatter(np.zeros(0), np.zeros(0), marker="o", facecolors="none", edgecolors="#ff3030",
                                    s=dot * 7.0, linewidths=2.2, zorder=4.9)
        fs = 10 if not small else 7.5
        self.dash_txt = [ax.text(0, 0, "", color="#ff6060", fontsize=fs, fontweight="bold", ha="center",
                                 va="bottom", zorder=7, clip_on=True) for _ in range(world.M)]
        self.catch_ring = ax.scatter(np.zeros(0), np.zeros(0), marker="o", facecolors="none", edgecolors="#ff2020",
                                     s=dot * 5, linewidths=2.6, zorder=6)
        self.catch_txt = [ax.text(0, 0, "", color="#ff4040", fontsize=fs, fontweight="bold", ha="center", va="top",
                                  zorder=7, clip_on=True) for _ in range(16)]
        self.status = ax.text(0.015, 0.985, "", transform=ax.transAxes, ha="left", va="top", color="white",
                              fontsize=10 if not small else 7.5, zorder=8,
                              bbox=dict(facecolor="black", alpha=0.6, edgecolor="none", pad=3))
        # 슬롯별 마지막 리스폰 스텝 (흐림용)
        n = len(frames[0]["pos"])
        self.last_done = np.full((len(frames), n), -10 ** 6, dtype=np.int64)
        cur = np.full(n, -10 ** 6, dtype=np.int64)
        for j, f in enumerate(frames):
            cur = np.where(f["done"], j, cur)
            self.last_done[j] = cur

    def update(self, k, frac=0.0):
        """스텝 k (0..K) 와 다음 스텝으로의 보간 비율 frac."""
        from matplotlib.colors import to_rgba
        from replay_v2 import BEH_COLORS

        fr = self.frames
        f = fr[k]
        nxt = fr[k + 1] if (frac > 0 and k + 1 < len(fr)) else None
        pos = f["pos"].copy()
        pred = f["pred"].copy()
        beh, phase = f["beh"], f["phase"]
        if nxt is not None:
            ok = ~nxt["done"]
            pos[ok] = (1 - frac) * f["pos"][ok] + frac * nxt["pos"][ok]
            pred = (1 - frac) * f["pred"] + frac * nxt["pred"]
            beh, phase = nxt["beh"], nxt["phase"]
        self.food.set_data(f["food"])
        self.night.set_alpha(0.5 * f["dark"])
        age = k - self.last_done[k]
        alpha = np.clip(0.2 + 0.8 * age / FADE, 0.2, 1.0)
        m = in_win(pos, self.c)
        bcol = np.array([to_rgba(c) for c in BEH_COLORS])
        cols = bcol[np.asarray(beh, dtype=np.int64)].copy()
        cols[:, 3] = alpha
        crouch = (beh == 2) & (phase == 1)
        edge = np.where(crouch[:, None], np.array(to_rgba("#e8f0ff")), np.array((0, 0, 0, 1.0)))
        edge[:, 3] = alpha
        self.herb.set_offsets(pos[m] if m.any() else np.empty((0, 2)))
        self.herb.set_facecolor(cols[m])
        self.herb.set_edgecolor(edge[m])
        self.herb.set_linewidths(np.where(crouch[m], 2.4, 0.6))
        fz = m & (beh == 3)
        self.bang.set_offsets(pos[fz] + np.array([0.9, 0.9]) if fz.any() else np.empty((0, 2)))
        head = f["head"]
        L = 1.4
        idx = np.flatnonzero(m)
        self._arrows(pos, head * L, m, alpha)
        # 꼬리: 같은 생애의 최근 TRAIL 스텝
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
        # 위협
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
        dashing = ((pt == W.PT_STALKER) & (f["stalk"] == W.ST_POUNCE)) | (player & (f["pmode"] == W.PM_CHARGE))
        self.dash_ring.set_offsets(off(dashing))
        pin = in_win(pred, self.c)
        for i, tx in enumerate(self.dash_txt):
            label = ""
            if pin[i]:
                if dashing[i]:
                    label = "돌진!"
                elif pt[i] == W.PT_STALKER and f["stalk"][i] == W.ST_EXHAUST:
                    label = "지침"
                elif asl[i]:
                    label = "잠"
            tx.set_text(label)
            if label:
                tx.set_position((pred[i, 0], pred[i, 1] + 1.6))
        psegs, pcols = [], []
        for i in range(len(pred)):
            pts = np.array([fr[j]["pred"][i] for j in range(max(k - PTRAIL, 0), k + 1)] + [pred[i]])
            if len(pts) > 2:
                psegs.append(pts)
                pcols.append((1.0, 0.45, 0.35, 0.55) if pt[i] != W.PT_PLAYER else (0.0, 0.9, 1.0, 0.55))
        self.ptrails.set_segments(psegs)
        if pcols:
            self.ptrails.set_color(pcols)
        # 잡힘
        cps = [fr[j]["caught"] for j in range(max(1, k - CATCH_SHOW + 1), k + 1) if len(fr[j]["caught"])]
        cps = np.concatenate(cps) if cps else np.empty((0, 2))
        cin = cps[in_win(cps, self.c)] if len(cps) else cps
        self.catch_ring.set_offsets(cin if len(cin) else np.empty((0, 2)))
        for j, tx in enumerate(self.catch_txt):
            if j < len(cin):
                tx.set_position((cin[j, 0], cin[j, 1] - 1.3))
                tx.set_text("잡힘")
            else:
                tx.set_text("")
        # 상태: 창 안 행동 수, 창 안 누적 잡힘
        bc = np.bincount(np.asarray(beh)[m].astype(np.int64), minlength=5)[:4]
        tot = sum(int(np.sum(in_win(fr[j]["caught"], self.c))) for j in range(1, k + 1) if len(fr[j]["caught"]))
        self.status.set_text(f"먹기 {bc[0]}  도망 {bc[1]}  숨기 {bc[2]}  얼기 {bc[3]}\n잡힘(누적) {tot}")
        return self

    def _arrows(self, pos, vec, m, alpha):
        n = len(pos)
        if self.arrows.N != n:
            self.arrows.remove()
            self.arrows = self.ax.quiver(pos[:, 0], pos[:, 1], vec[:, 0], vec[:, 1], angles="xy", scale_units="xy",
                                         scale=1.0, width=0.004, headwidth=3.0, headlength=3.5, headaxislength=3.0,
                                         color="white", zorder=3)
        v = np.where(m[:, None], vec, 0.0)
        self.arrows.set_offsets(pos)
        self.arrows.set_UVC(v[:, 0], v[:, 1])
        ac = np.ones((n, 4))
        ac[:, 3] = np.where(m, 0.55 * alpha, 0.0)
        self.arrows.set_color(ac)


def legend_handles():
    from matplotlib.lines import Line2D
    from replay_v2 import BEH_COLORS

    dot = dict(marker="o", ls="none", markersize=9, markeredgecolor="black")
    h = [Line2D([], [], label="먹기", markerfacecolor=BEH_COLORS[0], **dot),
         Line2D([], [], label="도망", markerfacecolor=BEH_COLORS[1], **dot),
         Line2D([], [], label="숨기(은신처로 감)", markerfacecolor=BEH_COLORS[2], **dot),
         Line2D([], [], label="숨기·웅크림(흰 테두리)", marker="o", ls="none", markersize=9,
                markerfacecolor=BEH_COLORS[2], markeredgecolor="#e8f0ff", markeredgewidth=2),
         Line2D([], [], label="얼기(!)", markerfacecolor=BEH_COLORS[3], **dot),
         Line2D([], [], label="추격형 포식자", marker="X", ls="none", markersize=11, markerfacecolor="#ff2d2d",
                markeredgecolor="white"),
         Line2D([], [], label="원거리형", marker="x", ls="none", markersize=10, color="#ff7a7a", markeredgewidth=2),
         Line2D([], [], label="잠행-돌진형", marker="X", ls="none", markersize=11, markerfacecolor="#ffb020",
                markeredgecolor="white"),
         Line2D([], [], label="플레이어형", marker="*", ls="none", markersize=15, markerfacecolor="#00e5ff",
                markeredgecolor="black"),
         Line2D([], [], label="돌진 중(빨간 원)", marker="o", ls="none", markersize=13, markerfacecolor="none",
                markeredgecolor="#ff3030", markeredgewidth=2),
         Line2D([], [], label="은신처", marker="o", ls="none", markersize=12, markerfacecolor="black",
                markeredgecolor="#7f8fd0")]
    return h


def render_scene(n, pick, world, branches, caption, out_mp4, step_sec):
    import matplotlib
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    from replay_v2 import BG, _ffmpeg_exe

    center = pick["center"]
    Wd, Hd = 18.0, 8.8
    fig = plt.figure(figsize=(Wd, Hd), dpi=100, facecolor=BG)
    side = 5.7
    gapx = (Wd - 3 * side) / 4
    y0 = 1.75
    panels = []
    for j, p in enumerate(POLS):
        ax = fig.add_axes(((gapx + j * (side + gapx)) / Wd, y0 / Hd, side / Wd, side / Hd))
        panels.append(MapPanel(ax, world, branches[p], center, TITLES[p]))
    head = fig.text(0.5, (y0 + side + 1.05) / Hd, "", color="white", fontsize=15, ha="center", va="center",
                    fontweight="bold")
    sub = fig.text(0.5, (y0 + side + 0.68) / Hd, "", color="#ffd34d", fontsize=12.5, ha="center", va="center")
    n_lines = caption.count("\n") + 1
    fig.text(0.5, (1.12 if n_lines <= 3 else 1.03) / Hd, caption, color="#eeeeee",
             fontsize=11.5 if n_lines <= 3 else 10.8, ha="center", va="center",
             linespacing=1.45 if n_lines <= 3 else 1.38)
    fig.legend(handles=legend_handles(), loc="lower center", ncol=11, fontsize=9, frameon=False,
               labelcolor="#dddddd", bbox_to_anchor=(0.5, 0.0), handletextpad=0.3, columnspacing=0.9)
    sched = [(0, 0.0)] * HOLD0
    for k in range(K):
        for s in range(SUB):
            sched.append((k, s / SUB))
    sched += [(K, 0.0)] * HOLD1
    t_ev = LEAD * step_sec

    def upd(i):
        k, fr = sched[i]
        for pnl in panels:
            pnl.update(k, fr)
        sec = (k + fr) * step_sec
        head.set_text(f"장면 {n} · 시드 {pick['seed']} · 갈라진 뒤 +{sec:4.1f}초 / {K * step_sec:.0f}초 (실시간 1배속)")
        if i < HOLD0:
            sub.set_text("같은 순간(같은 세계 사본)에서 세 정책으로 갈라 돌린다 — 지금은 세 칸이 똑같다")
        elif abs(sec - t_ev) <= 1.5:
            sub.set_text(f"+{t_ev:.1f}초: {KIND_KO[pick['kind']]} (RL 갈래 기준)")
        elif i >= len(sched) - HOLD1:
            sub.set_text("끝 (20초)")
        else:
            sub.set_text("")
        return []

    matplotlib.rcParams["animation.ffmpeg_path"] = _ffmpeg_exe()
    writer = animation.FFMpegWriter(fps=FPS, bitrate=3200)
    anim = animation.FuncAnimation(fig, upd, frames=len(sched), interval=1000 // FPS)
    anim.save(str(out_mp4), writer=writer, dpi=100)
    plt.close(fig)


def strip_moments(branches, focus):
    """PNG 띠 4개 시점: 갈라짐(0), 사건(LEAD), 세 갈래 행동이 가장 많이 다른 때(사건 8스텝 뒤~), 끝(K)."""
    focus = np.asarray(focus)
    dis = []
    for k in range(1, K + 1):
        b = [branches[p][k]["beh"][focus] for p in POLS]
        dis.append(np.mean((b[0] != b[1]) | (b[0] != b[2])))
    dis = np.convolve(np.asarray(dis), np.ones(5) / 5, mode="same")
    lo, hi = LEAD + 8, K - 15
    kp = int(lo + np.argmax(dis[lo - 1:hi - 1]))
    return [0, LEAD, kp, K]


def render_strip(n, pick, world, branches, moments, out_png, step_sec):
    import matplotlib.pyplot as plt
    from replay_v2 import BG

    side = 3.7
    lw, top, bot = 1.45, 0.75, 0.6
    Wd = lw + 4 * side + 0.15
    Hd = top + 3 * side + bot
    fig = plt.figure(figsize=(Wd, Hd), dpi=110, facecolor=BG)
    names = ("갈라진 순간(세 칸 같음)", "사건", "가장 다른 때", "끝")
    for r, p in enumerate(POLS):
        for cidx, k in enumerate(moments):
            ax = fig.add_axes(((lw + cidx * side + 0.05) / Wd, (bot + (2 - r) * side + 0.05) / Hd,
                               (side - 0.1) / Wd, (side - 0.42) / Hd))
            MapPanel(ax, world, branches[p], pick["center"], None, small=True).update(k, 0.0)
            ax.set_title(f"+{k * step_sec:.1f}초 · {names[cidx]}", color="#cccccc", fontsize=9, pad=2)
        fig.text(0.1 / Wd, (bot + (2 - r) * side + side / 2) / Hd, TITLES[p].replace(" (", "\n("), color="white",
                 fontsize=10.5, ha="left", va="center")
    fig.text(0.5, (Hd - 0.3) / Hd, f"장면 {n} · 시드 {pick['seed']} · {KIND_KO[pick['kind']]} (+{LEAD * step_sec:.1f}초, "
             f"RL 갈래 기준) · 같은 세계 사본에서 갈라 돌림", color="white", fontsize=12.5, ha="center", va="center")
    fig.text(0.5, 0.28 / Hd, "점 색: 초록 먹기 · 주황 도망 · 파랑 숨기(흰 테두리 = 은신처 안 웅크림) · 흰색+! 얼기 | "
             "빨간 X 추격형 · 주황 X 잠행-돌진형 · 하늘색 별 플레이어형 · 빨간 원 = 돌진 중 · 검은 원 = 은신처",
             color="#dddddd", fontsize=9.5, ha="center", va="center")
    fig.savefig(str(out_png), dpi=110, facecolor=BG)
    plt.close(fig)


def simulate_scene(cfg, pick, check=True):
    """RL 로 t0 까지 돌린 세계 사본에서 세 갈래를 기록한다. check 면 결정성도 확인한다."""
    seed, t0 = pick["seed"], pick["t0"]
    w = new_world(cfg, seed)
    pol = bound_policy("rl", w, seed)
    for _ in range(t0):
        step(w, pol)
    assert w.t == t0
    snap = copy.deepcopy(w)
    # 결정성: 같은 정책 두 벌이 비트 단위로 같은가 (세 정책 모두), RL 갈래가 본 궤적의 연장과 같은가
    # (갈래는 매 스텝 rep_peek 을 부르고 본 궤적의 연장은 부르지 않는다 — 같으면 rep_peek 이 궤적을 바꾸지 않는다는 확인도 된다)
    det, branches = {}, {}
    for p in POLS:
        a, _ = record_branch(snap, p, seed)
        if check:
            b, _ = record_branch(snap, p, seed)
            det[f"{p}_two_copies_identical"] = same_traj(a, b)
        branches[p] = a
    if check:
        cont = [_frame(w, np.empty((0, 2)))]
        for _ in range(K):
            step(w, pol)
            cont.append(_frame(w, np.empty((0, 2))))
        det["rl_branch_equals_original_run"] = same_traj(branches["rl"], cont)
        det["fsm_branch_differs_from_rl"] = not same_traj(branches["rl"], branches["fsm"])
        det["rbase_branch_differs_from_rl"] = not same_traj(branches["rl"], branches["rbase"])
    return snap, branches, det


def _render_one(job):
    n, pick, png_only, old_rec, n_cand = job
    cfg = load_cfg()
    from replay_v2 import step_seconds, video_info

    step_sec = step_seconds(cfg)
    seed, t0 = pick["seed"], pick["t0"]
    snap, branches, det = simulate_scene(cfg, pick, check=True)
    pick = dict(pick)
    pick["center"] = window_of(branches["rl"], pick, snap.size)
    summ = {p: branch_summary(branches[p], pick["focus"], pick["center"]) for p in POLS}
    for p in ("fsm", "rbase"):          # RL 과 처음 행동이 갈린 때 (창 안에 있는 개체, 같은 슬롯)
        fd = None
        for k in range(1, K + 1):
            a, b = branches["rl"][k], branches[p][k]
            m = in_win(a["pos"], pick["center"]) & in_win(b["pos"], pick["center"])
            if np.any(m & (a["beh"] != b["beh"])):
                fd = k
                break
        summ[p]["first_diff_from_rl_sec"] = None if fd is None else round(fd * step_sec, 2)
    moments = strip_moments(branches, pick["focus"])
    st = scene_stats(pick, branches, step_sec, moments)
    cap, cap_nums = make_caption(pick, st, step_sec, n_cand)
    png = OUT / f"scene{n}_seed{seed}_t{t0}.png"
    render_strip(n, pick, snap, branches, moments, png, step_sec)
    mp4 = OUT / f"scene{n}_seed{seed}_t{t0}.mp4"
    info = None
    if not png_only:
        t1 = time.time()
        render_scene(n, pick, snap, branches, cap, mp4, step_sec)
        info = video_info(mp4)
        info["render_sec"] = round(time.time() - t1, 1)
    rec = dict(n=n, tag=pick["tag"], seed=seed, t0=t0, t_e=pick["t_e"], kind=pick["kind"], threat=pick["threat"],
               n_focus=len(pick["focus"]), center=pick["center"], half=HALF, moments=moments, determinism=det,
               caption=cap, caption_in_video=not png_only, caption_numbers=cap_nums, screen_stats=st,
               search_metrics=pick["metrics"],
               search_metrics_note="탐색 단계 값(candidates.json). 갈라지기 전에 RL 이 고른 잠금(물려받은 스텝)이 세 갈래 "
                                   "비율에 함께 들어 있다 — 예: R_base 는 얼기를 고르지 않지만 장면 1 의 R_base 얼기 비율은 "
                                   "물려받은 것이다. 각 정책이 직접 고른 비율은 branch_summary.share_own",
               branch_summary=summ, png=str(png),
               mp4=str(mp4) if info else (old_rec or {}).get("mp4"), video=info or (old_rec or {}).get("video"))
    print(json.dumps({k: v for k, v in rec.items() if k not in ("search_metrics", "screen_stats")},
                     ensure_ascii=False), flush=True)
    return rec


def cmd_render(args):
    from concurrent.futures import ProcessPoolExecutor

    sel = json.loads((OUT / "select.json").read_text(encoding="utf-8"))
    n_cand = int(sel["summary"]["n_candidates"])
    old = {}
    if (OUT / "scenes.json").exists():
        old = {s["n"]: s for s in json.loads((OUT / "scenes.json").read_text(encoding="utf-8"))["scenes"]}
    jobs, results = [], []
    for n, pick in enumerate(sel["picks"], start=1):
        if args.only and n not in args.only:
            if n in old:
                results.append(old[n])
            continue
        jobs.append((n, pick, args.png_only, old.get(n), n_cand))
    with ProcessPoolExecutor(max_workers=max(1, min(args.workers, len(jobs) or 1))) as ex:
        results.extend(ex.map(_render_one, jobs))
    results.sort(key=lambda r: r["n"])
    notes = [
        "갈라진 순간(+0초)에 이미 잠금 중인 먹기 아닌 행동은 RL 이 갈라지기 전에 고른 것이라 세 칸에 똑같이 나온다. "
        "screen_stats.inherited_on_screen_until_sec 까지 화면에 남는다.",
        "갈라진 뒤에는 위치·위협·이웃도 달라진다(screen_stats.pos_gap_focus). 뒤로 갈수록 차이는 '두뇌의 선택'과 "
        "'달라진 상황'이 섞인 것이다. 사건 직후 2초의 같은 개체 불일치는 screen_stats.disagree_first_2s_after_event.",
        "자막 숫자(caption_numbers)는 기록된 프레임에서 코드로 센 값이고 captions.json 과 같다.",
    ]
    (OUT / "scenes.json").write_text(json.dumps(dict(lead=LEAD, k=K, half=HALF, fps=FPS, sub=SUB, notes=notes,
                                                     scenes=results), ensure_ascii=False, indent=1), encoding="utf-8")
    caps = {str(r["n"]): dict(caption=r.get("caption"), numbers=r.get("caption_numbers"),
                              in_video=r.get("caption_in_video")) for r in results}
    (OUT / "captions.json").write_text(json.dumps(dict(
        note="scenes.py render 가 기록된 프레임에서 숫자를 세어 만든 자막이다(손으로 적지 않는다). scenes.json 의 "
             "caption·caption_numbers 와 같다. in_video = 이 자막이 mp4 에 들어갔나.", **caps),
        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--seeds", nargs="*")
    s.add_argument("--workers", type=int, default=6)
    sub.add_parser("pick")
    r = sub.add_parser("render")
    r.add_argument("--only", type=int, nargs="*", help="장면 번호(1부터)만")
    r.add_argument("--png-only", action="store_true", help="PNG 띠와 지표만 (영상 없이)")
    r.add_argument("--workers", type=int, default=4, help="장면을 나란히 그릴 프로세스 수")
    args = ap.parse_args()
    if args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "pick":
        cmd_pick(args)
    else:
        cmd_render(args)
