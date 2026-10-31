"""v3 R2 결정적 확인표 T8 — 동족 경보 물결(M8)을 실제 세계 규칙으로 잰 표 (명세 `Docs/RL_Policy/RL_V3_R2_SPEC.md` 9절 T8,
사전 등록 `PREREG.md` 8절 '결정적 확인표'. 판정이 아니다 — 판정 전에 만들고 사전 등록 변경 기록이 인용한다).

    # herbivore_rl/ 에서 (몇 초)
    python results/v3/r2/wave_r2.py                 # → results/v3/r2/wave.json, wave.md

설정: W8 세계 `configs/v3_r2_w8_on.yaml`(세계 시드 12000 — 판정 시드 12160~12199 가 아니다)를 빌린다. 낮 고정, 은신처 없음,
먹이 가득. 위협 하나(잠행형, 하네스가 잠행·배회 속력을 0 으로 두어 제자리에 있다 — 물결만 보려고)를 개체 0 의 −x 쪽 실거리 9 에
둔다. 개체 0 만 위협을 본다(개체 0 은 위협 쪽을 보고, 나머지는 +x 쪽을 본다 — 등 뒤라 시야각 밖이다).
개체 0 은 첫 스텝에 FREEZE 로 들어간다(위협이 보이므로 홉 0). 나머지 개체는 먹다가(GRAZE) 시작하고 B0 잠금이 저절로 끝나지 않게
하네스가 붙잡는다 — 사건(E7)과 결정 지연(지연 {0, 3}, 모든 개체 같은 값)으로만 결정한다. 나머지 개체의 규칙:
  look  : 위협이 안 보이고 alarm_heard ≥ 0.4 & 은신처 거리 > 5 면 FREEZE (`repertoire_rules.NICHES['look']`), 아니면 R_base
  rbase : R_base(4, 0.9) — 경보를 읽지 않는다(무시)
배치: 한 줄 10마리(간격 s ∈ {4, 6, 8, 9}, 개체 i 는 x = i·s)와 4 × 3 격자(간격 6, 개체 0 이 모서리, 위협은 대각선 바깥).
max_hop {1, 2}, relay_window {30, 5}. 그 밖의 장면: 비명(줄 가운데 개체 바로 옆에 근접 추격형 — 잡힌 자리에서 홉 0, 점 = 잡은
위협의 위치, 리스폰한 슬롯의 경보 상태 0), 소문(위협 0마리, 개체 1 에 홉 0 경보를 심는다 — relay_window + alarm_steps 안에 꺼진다).
기록(개체별): 처음 받은 스텝·홉·ttl·alarm_heard, E7 스텝, FREEZE 진입 스텝, 받은 스텝의 마스크 판 3 FREEZE 열림(가능 조건),
실제 위협 쪽과의 시선 오차(점 방식 = 지금 규칙, 평행 복사 = 보낸 개체의 away 를 복사하는 비교 방식), 개체 0 의 메아리(홉 1 을
돌려받음)와 E7.
문턱 일치(골든 제외·경계 골든, 명세 6절): 줄 배치에서 어떤 두 개체의 거리(k·s)가 alarm_r 과 정확히 같은 장면(s 8 은 이웃, s 4 는
두 칸 건너)은 제목에 '‡'를 단다. 수신 판정이 '거리 ≤ alarm_r' 라 같으면 들리는 쪽이고, C++ float 에서 좌표가 정확히 표현되지
않으면 뒤집힐 수 있다. 그런 장면은 s ± SHIFT 판을 따로 재 '경계 옮긴 판'에 적는다 — 골든은 이 옮긴 판에서 고른다.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402  ← torch(rep_policy 마스크)보다 먼저
import numpy as np  # noqa: E402

CONFIG = "configs/v3_r2_w8_on.yaml"
SEED = 12000
D_THREAT = 9.0
STEPS = 60
N_LINE = 10
HOLD = 10 ** 6                       # 하네스가 붙잡는 잠금(사건으로만 결정)
SHIFT = 0.01                         # 문턱 일치 장면의 경계 옮긴 판(s ± SHIFT)


def _cfg(**alarm):
    from env_v2.config import load_v2_config

    cfg = load_v2_config(ROOT / CONFIG)
    if alarm:
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        f["alarm"] = dict(f["alarm"], **alarm)
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    return cfg


def _layout(kind: str, s: float, c: np.ndarray):
    """(개체 위치 (K, 2), heading (K, 2), 위협 위치) — 개체 0 이 위협 쪽을 본다."""
    if kind == "line":
        pos = np.array([c + [i * s, 0.0] for i in range(N_LINE)])
        q = c + [-D_THREAT, 0.0]
    else:                                   # 4 × 3 격자, 개체 0 은 (0, 0) 모서리, 위협은 대각선 바깥
        pos = np.array([c + [ix * s, iy * s] for iy in range(3) for ix in range(4)])
        q = c - D_THREAT / math.sqrt(2.0) * np.array([1.0, 1.0])
    head = np.tile([1.0, 0.0], (len(pos), 1))
    if kind == "grid":
        head[:] = [math.sqrt(0.5), math.sqrt(0.5)]
    u = q - pos[0]
    head[0] = u / np.linalg.norm(u)
    return pos, head, q


def setup(cfg, kind: str, s: float, jitter: int, threat: str = "stalker"):
    """개체 K 마리(줄·격자)와 위협 하나. 나머지 개체는 멀리 구석에 둔다(듣지도 보지도 않는다)."""
    from env_v2 import repertoire as rep
    from env_v2.world import PM_STALK, PT_CHASER, PT_STALKER, World

    w = World(cfg, seeds=[SEED])
    w.day_fixed = True
    w._daynight_update()
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    w.food[:] = 1.0
    w.food_cap[:] = 1.0
    c = np.array([w.size * 0.4, w.size * 0.5])
    pos, head, q = _layout(kind, s, c)
    K = len(pos)
    w.pos[:] = [0.5, 0.5]
    w.pos[:K] = pos
    w.head[:K] = head
    th = dict(w._th)
    if threat == "none":
        w.M = w.M_base = 0
        w.pred_pos = np.zeros((0, 2))
        w.pred_head = np.zeros((0, 2))
        for k in ("pred_ranged", "_pred_ranged_v1", "pred_nocturnal", "pred_asleep"):
            setattr(w, k, np.zeros(0, dtype=bool))
        w.pred_speed = w.pred_catch_r = w._pred_speed_mult = np.zeros(0)
        w.pred_cd = np.zeros(0, dtype=np.int32)
        w.pred_type = np.zeros(0, dtype=np.int8)
        w.pred_vel = np.zeros((0, 2))
    else:
        w.M = w.M_base = 1
        if threat == "stalker":
            w.pred_pos = np.array([q])
            th.update(stalk_speed=0.0)      # 제자리 잠행형(물결만 본다)
        else:                               # 비명 장면: 줄 가운데 개체 바로 옆의 근접 추격형
            w.pred_pos = np.array([pos[5] + [0.0, 0.5]])
        w.pred_head = np.array([[1.0, 0.0]])
        w.pred_ranged = np.zeros(1, dtype=bool)
        w._pred_ranged_v1 = np.zeros(1, dtype=bool)
        w.pred_speed = np.zeros(1)
        w.pred_catch_r = np.full(1, w.cfg.pred_melee_catch_r)
        w.pred_cd = np.zeros(1, dtype=np.int32)
        w.pred_type = np.array([PT_STALKER if threat == "stalker" else PT_CHASER], dtype=np.int8)
        w.pred_nocturnal = np.ones(1, dtype=bool)
        w.pred_asleep = np.zeros(1, dtype=bool)
        w._pred_speed_mult = np.ones(1)
        w.pred_vel = np.zeros((1, 2))
    w._th = th
    w.pred_is_player = w.pred_type == 99
    w.player_present = False
    w.stalk_state = np.zeros(w.M, dtype=np.int8)
    w.stalk_left = np.zeros(w.M, dtype=np.int64)
    w.player_mode = np.full(w.M, PM_STALK, dtype=np.int8)
    w.player_left = np.full(w.M, 10 ** 6, dtype=np.int64)
    w._alarm_reset()
    w._reset_stats()
    rs, rp = w._rs, w._rp
    # 사건 기준값을 하네스가 만든 지금 상태에 맞춘다: 위협은 '처음 나타난' 것으로(직전에 본 위협 없음 — 보이면 E1), 어둠·
    # 에너지는 지금 값(원래 세계의 reset 값과 달라 첫 스텝에 가짜 E4·E5 가 나지 않게)
    rs.prev_pc[:] = 0
    rs.prev_near[:] = False
    rs.prev_fast[:] = False
    rs.prev_low[:] = w.energy / w.cfg.max_energy < rp["event_energy"]
    rs.prev_dark[:] = w.dark >= rp["event_dark"]
    rs.ev_wait[:] = -1
    rs.jitter[:] = jitter
    rs.lock_left[:] = HOLD
    rs.lock_left[0] = 0
    w._g = w._geometry()
    rep.perceive(rs, rp, w._g)
    w._obs = w._obs_from(w._g)
    return w, K, q


def _ang(u, v) -> float:
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu <= 0.0 or nv <= 0.0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.dot(u, v) / (nu * nv), -1.0, 1.0))))


def scene(kind: str, s: float, rule: str, jitter: int, max_hop: int = 2, relay_window: int = 30,
          threat: str = "stalker", plant: bool = False) -> dict:
    """한 장면. 반환: 개체별 기록, 스텝별 방출, 메아리·비명·소문 확인 값."""
    import repertoire_rules as rr
    from env_v2 import repertoire as rep
    from env_v2.rep_policy import feasible_mask

    cfg = _cfg(max_hop=max_hop, relay_window=relay_window)
    w, K, q = setup(cfg, kind, s, jitter, threat)
    rs = w._rs
    if plant:                               # 소문: 개체 1 이 방금 홉 0 경보를 받은 것처럼 둔다(위협 0마리)
        rs.al_ttl[1], rs.al_hop[1], rs.al_t0[1] = w._al["alarm_steps"], 0, 0
        rs.al_pt[1] = w.pos[1] + [-D_THREAT, 0.0]
        rs.alarm_new[1] = True
        w._obs = w._obs_from(w._g)
    spec = rr.rule_spec(cfg, 4.0, 0.9, x="look" if rule == "look" else None, mode="niche")
    pol = None
    from env_v2 import rollout as ro

    pol = ro.build_policy(spec, 0)
    rec = {i: dict(recv_t=None, recv_hop=None, recv_ttl=None, recv_level=None, recv_from=None, e7_t=None, freeze_t=None,
                   emit=[], mask_freeze_at_recv=None, err_pt=None, err_copy=None) for i in range(K)}
    emits = []
    echo = dict(hop1_heard=False, e7=False)
    last_alarm_t = None
    cry = None
    for t in range(STEPS):
        req = np.asarray(pol(w.observe()), dtype=np.float64)
        if t == 0 and threat == "stalker":
            req[0, 0] = rep.FREEZE              # 개체 0 은 위협을 보고 언다(홉 0)
        req[K:, 0] = rep.GRAZE
        away_before = rs.away.copy()
        _, _, done, _ = w.step(req)
        o = w.observe()
        fm = feasible_mask(o, w.obs_names)
        em = np.flatnonzero(w.alarm_emit >= 0)
        if len(em):
            emits.append(dict(t=t, who=[int(i) for i in em], hop=[int(w.alarm_emit[i]) for i in em]))
        if (rs.al_ttl > 0).any():
            last_alarm_t = t
        if threat == "chaser" and done[:K].any() and cry is None:
            v = int(np.flatnonzero(done[:K])[0])
            nb = [i for i in range(K) if i != v and w.alarm_from[i] == v]
            cry = dict(t=t, victim=v, pred_pos=[round(float(x), 3) for x in w.pred_pos[0]],
                       pt_of_receivers=[[round(float(x), 3) for x in w.alarm_pt[i]] for i in nb], receivers=nb,
                       hop=int(w.alarm_emit[v]), victim_state_after_respawn=dict(
                           ttl=int(rs.al_ttl[v]), hop=int(rs.al_hop[v]), seq=int(rs.alarm_seq[v]),
                           alarm_new=bool(rs.alarm_new[v]), obs_alarm_heard=float(o[v, w._obs_alarm])))
        for i in range(K):
            r = rec[i]
            if w.alarm_emit[i] >= 0:
                r["emit"].append([t, int(w.alarm_emit[i])])
            if w.alarm_e7[i] and r["e7_t"] is None:
                r["e7_t"] = t
                if i == 0:
                    echo["e7"] = True
            if w.behavior[i] == rep.FREEZE and r["freeze_t"] is None:
                r["freeze_t"] = t
            if i == 0 and t > 0 and w.alarm_from[0] >= 0:
                echo["hop1_heard"] = True
            if r["recv_t"] is None and w.alarm_hop[i] >= 0 and (w.alarm_from[i] >= 0 or plant and i == 1):
                r.update(recv_t=t, recv_hop=int(w.alarm_hop[i]), recv_ttl=int(rs.al_ttl[i]),
                         recv_level=round(float(w.alarm_level[i]), 4), recv_from=int(w.alarm_from[i]),
                         mask_freeze_at_recv=bool(fm[i, rep.FREEZE]))
                if threat == "stalker" and w.alarm_from[i] >= 0:
                    true = q - w.pos[i]
                    r["err_pt"] = round(_ang(w.alarm_pt[i] - w.pos[i], true), 2)
                    r["err_copy"] = round(_ang(-away_before[w.alarm_from[i]] if (away_before[w.alarm_from[i]] != 0).any()
                                               else -rs.away[w.alarm_from[i]], true), 2)
    out = dict(kind=kind, s=s, rule=rule, jitter=jitter, max_hop=max_hop, relay_window=relay_window, threat=threat,
               agents=rec, emits=emits, echo=echo, last_alarm_t=last_alarm_t, cry=cry,
               stats={k: (None if isinstance(v, float) and v != v else v) for k, v in w.alarm_stats().items()})
    return out


def run_all() -> dict:
    res = {}
    for s in (4.0, 6.0, 8.0, 9.0):
        for mh in (1, 2):
            for j in (0, 3):
                for rule in ("look", "rbase"):
                    res[f"line|s{s:g}|hop{mh}|j{j}|{rule}|rw30"] = scene("line", s, rule, j, mh)
    for j in (0, 3):
        res[f"line|s6|hop2|j{j}|look|rw5"] = scene("line", 6.0, "look", j, 2, relay_window=5)
        res[f"grid|s6|hop2|j{j}|look|rw30"] = scene("grid", 6.0, "look", j, 2)
    res["cry|line|s6|hop2|j0|look|rw30"] = scene("line", 6.0, "look", 0, 2, threat="chaser")
    res["rumor|line|s6|hop2|j0|look|rw30"] = scene("line", 6.0, "look", 0, 2, threat="none", plant=True)
    r = _alarm_r()
    for s in (4.0, 8.0):                    # 경계 옮긴 판(문턱 일치 장면만)
        if not line_edge(s, r):
            continue
        for sg in (-1, 1):
            sv = round(s + sg * SHIFT, 6)
            for j in (0, 3):
                res[f"shift|line|s{sv:g}|hop2|j{j}|look|rw30"] = scene("line", sv, "look", j, 2)
    return res


def _alarm_r() -> float:
    return float(_cfg().v2["features"]["alarm"]["alarm_r"])


def line_edge(s: float, alarm_r: float) -> bool:
    """줄 배치(간격 s)에서 어떤 두 개체의 거리 k·s 가 alarm_r 과 정확히 같은가(1e-9 안)."""
    return any(abs(k * s - alarm_r) < 1e-9 for k in range(1, N_LINE))


def _agent_row(i, r) -> str:
    def f(x, fmt="{}"):
        return "—" if x is None else fmt.format(x)
    return (f"| {i} | {f(r['recv_t'])} | {f(r['recv_hop'])} | {f(r['recv_ttl'])} | {f(r['recv_level'], '{:.2f}')} | "
            f"{f(r['recv_from'])} | {'열림' if r['mask_freeze_at_recv'] else ('닫힘' if r['mask_freeze_at_recv'] is not None else '—')} | "
            f"{f(r['e7_t'])} | {f(r['freeze_t'])} | {' '.join(f'{t}:h{h}' for t, h in r['emit']) or '—'} | "
            f"{f(r['err_pt'], '{:.1f}')} | {f(r['err_copy'], '{:.1f}')} |")


def highlights(res: dict) -> list[str]:
    L = []
    for s in (4.0, 6.0, 8.0):
        for j in (0, 3):
            v = res[f"line|s{s:g}|hop2|j{j}|look|rw30"]["agents"]
            L.append(f"- 줄 s {s:g}, max_hop 2, 지연 {j}, look: 개체 1 받음 t{v[1]['recv_t']}·홉 {v[1]['recv_hop']}·세기 "
                     f"{v[1]['recv_level']}·FREEZE t{v[1]['freeze_t']}, 개체 2 받음 t{v[2]['recv_t']}·홉 {v[2]['recv_hop']}·세기 "
                     f"{v[2]['recv_level']}·FREEZE t{v[2]['freeze_t']}, 개체 3 받음 t{v[3]['recv_t']}·홉 {v[3]['recv_hop']}·세기 "
                     f"{v[3]['recv_level']}·E7 {v[3]['e7_t']}·마스크 FREEZE {'열림' if v[3]['mask_freeze_at_recv'] else '닫힘'}")
    for mh in (1, 2):
        v = res[f"line|s9|hop{mh}|j0|look|rw30"]["agents"]
        L.append(f"- 줄 s 9, max_hop {mh}: 받은 개체 {[i for i in v if v[i]['recv_t'] is not None and i != 0] or '없음'}")
    v = res["line|s6|hop1|j0|look|rw30"]["agents"]
    L.append(f"- 줄 s 6, max_hop 1: 받은 개체 {[i for i in v if v[i]['recv_t'] is not None]}, 홉 "
             f"{[v[i]['recv_hop'] for i in v if v[i]['recv_t'] is not None]}")
    for j in (0, 3):
        v = res[f"line|s6|hop2|j{j}|look|rw30"]["agents"]
        steps = [v[i]["recv_t"] for i in (1, 2, 3)]
        L.append(f"- 홉 하나의 시간(줄 s 6, 지연 {j}): 개체 1·2·3 받은 스텝 {steps} — 차 "
                 f"{[b - a for a, b in zip(steps, steps[1:]) if a is not None and b is not None]} (1 + 지연 = {1 + j})")
    for j in (0, 3):
        a = res[f"line|s6|hop2|j{j}|look|rw30"]["agents"]
        g = res[f"grid|s6|hop2|j{j}|look|rw30"]["agents"]
        ep = [a[i]["err_pt"] for i in a if a[i]["err_pt"] is not None]
        gp = [g[i]["err_pt"] for i in g if g[i]["err_pt"] is not None]
        gc = [g[i]["err_copy"] for i in g if g[i]["err_copy"] is not None]
        L.append(f"- 시선 오차(지연 {j}): 줄 점 방식 최대 {max(ep) if ep else '—'}°, 격자 점 방식 평균 "
                 f"{np.mean(gp) if gp else float('nan'):.1f}° 대 평행 복사 평균 {np.mean(gc) if gc else float('nan'):.1f}°"
                 f"(받은 개체 {len(gp)})")
    for j in (0, 3):
        e = res[f"line|s6|hop2|j{j}|look|rw30"]["echo"]
        L.append(f"- 메아리(줄 s 6, 지연 {j}): 개체 0 이 홉 1 을 받아들임 {e['hop1_heard']}, 개체 0 의 E7 {e['e7']}")
    for j in (0, 3):
        a = res[f"line|s6|hop2|j{j}|look|rw30"]
        b = res[f"line|s6|hop2|j{j}|look|rw5"]
        L.append(f"- relay_window 30 대 5 (줄 s 6, 지연 {j}): 방출 홉 {sorted({h for e in a['emits'] for h in e['hop']})} 대 "
                 f"{sorted({h for e in b['emits'] for h in e['hop']})}, 받은 개체 수 "
                 f"{sum(v['recv_t'] is not None for v in a['agents'].values())} 대 "
                 f"{sum(v['recv_t'] is not None for v in b['agents'].values())}")
    for j in (0, 3):
        v = res[f"line|s6|hop2|j{j}|rbase|rw30"]["agents"]
        L.append(f"- 무시 줄(R_base, s 6, 지연 {j}): 받은 개체 {[i for i in v if v[i]['recv_t'] is not None and i != 0]}, "
                 f"홉 {sorted({v[i]['recv_hop'] for i in v if v[i]['recv_t'] is not None and i != 0})}, 얼어 붙은 개체 "
                 f"{[i for i in v if v[i]['freeze_t'] is not None and i != 0] or '없음'}")
    c = res["cry|line|s6|hop2|j0|look|rw30"]["cry"]
    if c:
        L.append(f"- 비명: 개체 {c['victim']} 가 t{c['t']} 에 잡혀 홉 {c['hop']} 을 냈다. 잡은 위협 위치 {c['pred_pos']}, 받은 개체 "
                 f"{c['receivers']} 의 점 {c['pt_of_receivers']}. 리스폰한 슬롯의 경보 상태 {c['victim_state_after_respawn']}")
    r = res["rumor|line|s6|hop2|j0|look|rw30"]
    L.append(f"- 소문(위협 0마리, 개체 1 에 심음): 방출 {[(e['t'], e['hop']) for e in r['emits']]}, 마지막으로 경보가 남은 스텝 "
             f"{r['last_alarm_t']} (relay_window + alarm_steps = 45 안)")
    for s in (4.0, 8.0):
        for j in (0, 3):
            row = []
            for sv in (round(s - SHIFT, 6), s, round(s + SHIFT, 6)):
                key = (f"shift|line|s{sv:g}|hop2|j{j}|look|rw30" if sv != s else f"line|s{s:g}|hop2|j{j}|look|rw30")
                if key not in res:
                    continue
                v = res[key]["agents"]
                got = [i for i in v if v[i]["recv_t"] is not None and i != 0]
                row.append(f"s {sv:g}{' ‡' if sv == s else ''} → 받은 개체 {got}")
            if len(row) > 1:
                L.append(f"- 경계 옮긴 판(줄, max_hop 2, 지연 {j}): " + "; ".join(row))
    return L


def summary_md(res: dict) -> str:
    al = _cfg().v2["features"]["alarm"]
    L = ["# v3 R2 결정적 확인표 T8 — 동족 경보 물결 (M8)", "",
         f"설정 {CONFIG}: alarm_r {al['alarm_r']}, alarm_steps {al['alarm_steps']}, hop_gain {al['hop_gain']}, event_alarm "
         f"{al['event_alarm']}, 비명 {al['on_catch']}. 장면마다 max_hop·relay_window 를 덮는다. 세계 시드 {SEED}(판정 시드 아님). "
         "판정이 아니다.", "",
         "개체 0 이 첫 스텝(t0)에 위협을 보고 언다(홉 0). 받은 스텝 = E′ 에서 경보를 받아들인 스텝(그 스텝 끝 관측의 alarm_heard 가"
         " '세기'), E7 = 다음 스텝 arbitrate 의 사건, FREEZE = 실행 행동이 FREEZE 가 된 스텝, 방출 = 't:h홉'. 마스크 = 받은 스텝 끝"
         " 관측의 판 3 FREEZE 가능(alarm_heard ≥ 0.4). 시선 오차 = 받은 순간 경보 방향과 실제 위협 쪽의 각(점 방식, 평행 복사 방식). "
         f"'‡' = 문턱 일치 장면(두 개체의 거리가 alarm_r 과 정확히 같다 — 골든에서 빼고 s ± {SHIFT:g} 판에서 고른다, 명세 6절).", "",
         "## 반드시 보일 것 (명세 9절 T8) — 표에서 읽은 값", ""]
    L += highlights(res)
    head = ("| 개체 | 받은 스텝 | 홉 | ttl | 세기 | 보낸 개체 | 마스크 FREEZE | E7 | FREEZE | 방출 | 시선 오차 점 | 시선 오차 복사 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|")
    r = float(al["alarm_r"])
    for key, v in res.items():
        mark = " ‡ 문턱 일치(두 개체의 거리 = alarm_r)" if v["kind"] == "line" and line_edge(float(v["s"]), r) else ""
        L += ["", f"## {key}{mark}", "", *head]
        L += [_agent_row(i, r) for i, r in v["agents"].items()]
        L += ["", f"통계: 방출 홉 0·1·2 = {v['stats']['emit_h0']:g}·{v['stats']['emit_h1']:g}·{v['stats']['emit_h2']:g}, 비명 "
              f"{v['stats']['cry_n']:g}, E7 {v['stats']['e7_n']:g}, 방향 받은 개체 {v['stats']['dir_n']:g}, 점 방식 ±30° 안 "
              f"{v['stats']['dir_ok_pt']}, 복사 방식 {v['stats']['dir_ok_copy']}"]
    return "\n".join(L) + "\n"


def main() -> int:
    res = run_all()
    out = HERE.parent
    (out / "wave.json").write_text(json.dumps(dict(config=CONFIG, seed=SEED, d_threat=D_THREAT, steps=STEPS, scenes=res),
                                              separators=(",", ":"), default=str), encoding="utf-8")
    md = summary_md(res)
    (out / "wave.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
