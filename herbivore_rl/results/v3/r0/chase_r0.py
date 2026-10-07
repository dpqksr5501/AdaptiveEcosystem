"""v3 R0 결정적 추격표 — M1(정지 탐지)·M2(놀람 정지)·M3(잠행-돌진)·플레이어 돌진을 실제 세계 규칙으로 합쳐 잰 표
(설계 검토 1-4·'반드시 바꿀 것' 2, R0 구현 검토 10-07. 사전 등록 `PREREG.md` 변경 기록이 이 표를 인용한다).

    # herbivore_rl/ 에서 (몇십 초)
    python results/v3/r0/chase_r0.py                 # → results/v3/r0/chase.json, chase.md

설정: 판정 설정 `configs/v3_r0_on.yaml` 세계(시드 SEEDS)를 빌려 개체 0 과 위협 하나만 남긴다 — 낮 고정(d = 0), 은신처 없음,
먹이 가득(GRAZE 는 머리 숙여 정지해 먹는다), 개체 0 은 맵 가운데에서 위협 쪽을 본다(위협은 −x 쪽 거리 D0, 개체 쪽을 본다).
나머지 개체는 구석에 둔다. 위협: 잠행형(배회 상태에서 시작, 근접 포획 거리 1) 또는 플레이어(잠행 모드에서 시작).
규칙: 시작 행동 B0(GRAZE 또는 FREEZE)을 요청하다가 보이는 가장 가까운 위협의 관측 거리 ≤ θ 이거나 접근 관측 ≥ a 가 되면
FLEE 를 요청하고 그 뒤로 계속 FLEE 를 요청한다('도망 안 함'은 B0 를 끝까지).
결정: '잠금 없음' = 시작 잠금 0(매 스텝 결정 — 가장 빠른 반응), '잠금 중' = B0 에 막 들어온 상태(잠금 12)라 사건(E1·E2…)
과 개체 결정 지연 0~3 으로만 결정한다(지연마다 따로 잰다).
결과: 첫 공격(잠행형의 돌진 1회 — 탈진이 시작되면 끝, 플레이어의 돌진 1회 — 휴식이 시작되면 끝) 안에 잡히면 '잡힘'.
세계 시드마다 맵 크기·포식자 속도 배수가 달라 칸 값은 '잡힌 수 / 시행 수'다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

CONFIG = "configs/v3_r0_on.yaml"
SEEDS = (12000, 12001, 12002)
D0 = 7.5                     # 시작 거리: GRAZE(×1)·FREEZE(×1.8 → 13.5)가 모두 포식자 시야 14 안이라 처음부터 표적이다
THETAS = (8.0, 7.0, 6.0, 5.0, 4.0, 3.0)
APPROACHES = (0.6, 0.75, 0.9)
MAX_STEPS = 80
JITTERS = (0, 1, 2, 3)


def setup(cfg, seed: int, kind: str, beh0: int, locked: bool, jitter: int):
    from env_v2 import repertoire as rep
    from env_v2.world import PM_STALK, PT_PLAYER, PT_STALKER, World

    w = World(cfg, seeds=[seed])
    w.day_fixed = True
    w._daynight_update()
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    w.food[:] = 1.0
    w.food_cap[:] = 1.0
    c = np.array([w.size / 2, w.size / 2])
    w.pos[:] = [0.5, 0.5]
    w.pos[0] = c
    w.head[0] = [-1.0, 0.0]
    player = kind == "player"
    w.M, w.M_base = 1, 0 if player else 1
    w.pred_pos = np.array([c + [-D0, 0.0]])
    w.pred_head = np.array([[1.0, 0.0]])
    w.pred_ranged = np.zeros(1, dtype=bool)
    w._pred_ranged_v1 = np.zeros(1, dtype=bool)
    w.pred_speed = np.full(1, w.cfg.herb_speed * w.pred_speed_mult)
    w.pred_catch_r = np.full(1, w._th["player_catch_r"] if player else w.cfg.pred_melee_catch_r)
    w.pred_cd = np.zeros(1, dtype=np.int32)
    w.pred_vel = np.zeros((1, 2))
    w.pred_type = np.array([PT_PLAYER if player else PT_STALKER], dtype=np.int8)
    w.pred_is_player = w.pred_type == PT_PLAYER
    w.player_present = player
    w.stalk_state = np.zeros(1, dtype=np.int8)
    w.stalk_left = np.zeros(1, dtype=np.int64)
    w.player_mode = np.full(1, PM_STALK, dtype=np.int8)
    w.player_left = np.full(1, 10 ** 6, dtype=np.int64)
    w.pred_nocturnal = np.ones(1, dtype=bool)
    w.pred_asleep = np.zeros(1, dtype=bool)
    w._pred_speed_mult = np.ones(1)
    rs, rp = w._rs, w._rp
    rs.behavior[0] = beh0
    rs.lock_left[0] = rp["locks"][beh0] if locked else 0
    rs.jitter[0] = jitter
    see = rp["graze_head_down"] if beh0 == rep.GRAZE else 1.0
    w._rep_see[0] = w._rep_see_last[0] = see
    w._g = w._geometry()
    rep.perceive(rs, rp, w._g)
    w._obs = w._obs_from(w._g)
    return w


def chase(cfg, seed, kind, beh0, trigger, locked=False, jitter=0) -> dict:
    """한 시행. trigger = ("dist", θ) | ("approach", a) | ("never", None). 반환: caught, flee_t·flee_d(FLEE 요청을 처음 낸
    스텝·그때 실거리), attack_d(돌진 시작 때 실거리), steps."""
    from env_v2 import repertoire as rep
    from env_v2.world import PM_CHARGE, PM_REST, ST_EXHAUST, ST_POUNCE

    w = setup(cfg, seed, kind, beh0, locked, jitter)
    want_flee = False
    out = dict(caught=False, flee_t=None, flee_d=None, attack_d=None, steps=MAX_STEPS)
    player = kind == "player"
    for t in range(MAX_STEPS):
        g = w._g
        seen = g["pred_count"][0] > 0
        mode, x = trigger
        if seen and not want_flee:
            if (mode == "dist" and g["d_pred_min"][0] <= x) or (mode == "approach" and g["pred_approach"][0] >= x):
                want_flee = True
                out["flee_t"], out["flee_d"] = t, round(float(np.linalg.norm(w.pred_pos[0] - w.pos[0])), 2)
        req = np.full((w.N, 1), float(rep.GRAZE))
        req[0, 0] = rep.FLEE if want_flee else beh0
        d_before = float(np.linalg.norm(w.pred_pos[0] - w.pos[0]))
        attacking0 = (w.player_mode[0] == PM_CHARGE) if player else (w.stalk_state[0] == ST_POUNCE)
        _, _, done, _ = w.step(req)
        attacking = (w.player_mode[0] == PM_CHARGE) if player else (w.stalk_state[0] == ST_POUNCE)
        if out["attack_d"] is None and attacking and not attacking0:
            out["attack_d"] = round(d_before, 2)
        if done[0]:
            out.update(caught=True, steps=t)
            break
        ended = (w.player_mode[0] == PM_REST) if player else (w.stalk_state[0] == ST_EXHAUST)
        if ended:
            out["steps"] = t
            break
    return out


def table(cfg) -> dict:
    from env_v2 import repertoire as rep

    triggers = ([("dist", th) for th in THETAS] + [("approach", a) for a in APPROACHES] + [("never", None)])
    res = {}
    for kind in ("stalker", "player"):
        for bname, b0 in (("graze", rep.GRAZE), ("freeze", rep.FREEZE)):
            for locked in (False, True):
                for mode, x in triggers:
                    js = JITTERS if locked else (0,)
                    runs = [chase(cfg, s, kind, b0, (mode, x), locked, j) for s in SEEDS for j in js]
                    key = f"{kind}|{bname}|{'locked' if locked else 'free'}|{mode}|{x if x is not None else '-'}"
                    res[key] = dict(caught=sum(r["caught"] for r in runs), n=len(runs), runs=runs)
    return res


def summary_md(res: dict, cfg) -> str:
    th = cfg.v2["features"]["threats"]
    rp = cfg.v2["features"]["repertoire"]
    L = ["# v3 R0 결정적 추격표 (M1·M2·M3·플레이어 돌진)", "",
         f"설정 {CONFIG}: 잠행 ×{th['stalk_speed']}·돌진 ×{th['pounce_speed']} {th['pounce_steps']}스텝(체감 거리 ≤ "
         f"{th['stalk_dist']}), 플레이어 잠행 ×{th['player_speeds'][1]}·돌진 ×{th['player_speeds'][2]} "
         f"{th['player_charge_steps']}스텝(≤ {th['player_charge_dist']}), c_still {rp['c_still']}, 놀람 {rp['startle_steps']}스텝,"
         f" 고개 숙임 ×{rp['graze_head_down']}. 시작 거리 {D0}, 낮, 은신처 없음. 세계 시드 {list(SEEDS)}.", "",
         "값 = 첫 공격에 잡힌 수 / 시행 수. '잠금 없음'은 매 스텝 결정, '잠금 중'은 시작 행동 잠금 12 에서 사건으로만 결정"
         "(결정 지연 0~3 마다 시행). 거리 θ = 보이는 위협의 관측 거리가 θ 이하가 되면 FLEE, 접근 a = 접근 관측이 a 이상이 되면"
         " FLEE.", ""]
    head = [f"거리 {x:g}" for x in THETAS] + [f"접근 {a:g}" for a in APPROACHES] + ["도망 안 함"]
    L += ["| 위협 | 시작 행동 | 결정 | " + " | ".join(head) + " |", "|---" * (3 + len(head)) + "|"]
    keys = ([("dist", x) for x in THETAS] + [("approach", a) for a in APPROACHES] + [("never", "-")])
    for kind, kn in (("stalker", "잠행형"), ("player", "플레이어")):
        for b, bn in (("graze", "GRAZE(정지 먹기)"), ("freeze", "FREEZE")):
            for lk, ln in (("free", "잠금 없음"), ("locked", "잠금 중")):
                cells = []
                for mode, x in keys:
                    v = res[f"{kind}|{b}|{lk}|{mode}|{x}"]
                    cells.append(f"{v['caught']}/{v['n']}")
                L.append(f"| {kn} | {bn} | {ln} | " + " | ".join(cells) + " |")
    L += ["", "## 읽기", ""]
    for kind, kn in (("stalker", "잠행형"), ("player", "플레이어")):
        for b, bn in (("graze", "GRAZE"), ("freeze", "FREEZE")):
            safe = [x for x in THETAS if res[f"{kind}|{b}|free|dist|{x}"]["caught"] == 0]
            dead = [x for x in THETAS if res[f"{kind}|{b}|free|dist|{x}"]["caught"] > 0]
            att = [r["attack_d"] for r in res[f"{kind}|{b}|free|never|-"]["runs"] if r["attack_d"] is not None]
            L.append(f"- {kn}·{bn}(잠금 없음): 늘 사는 도망 시작 거리 θ ∈ {safe or '없음'}, 잡히는 θ ∈ {dead or '없음'}. "
                     f"도망 안 할 때 돌진 시작 실거리 {att or '없음'}.")
    return "\n".join(L) + "\n"


def main() -> int:
    from env_v2.config import load_v2_config

    cfg = load_v2_config(ROOT / CONFIG)
    res = table(cfg)
    out = HERE.parent
    (out / "chase.json").write_text(json.dumps(dict(config=CONFIG, seeds=list(SEEDS), d0=D0, table=res), indent=1),
                                    encoding="utf-8")
    md = summary_md(res, cfg)
    (out / "chase.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
