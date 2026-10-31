"""v3 R2 결정적 확인표 T7 — 노려보기 대치(M7)를 실제 세계 규칙으로 잰 표 (명세 `Docs/RL_Policy/RL_V3_R2_SPEC.md` 9절 T7,
사전 등록 `PREREG.md` 8절 '결정적 확인표'. 판정이 아니다 — 판정 전에 만들고 사전 등록 변경 기록이 인용한다).

    # herbivore_rl/ 에서 (몇 분)
    python results/v3/r2/standoff_r2.py --workers 8          # → results/v3/r2/standoff.json, standoff.md

명세는 이 도구를 `chase_r2.py` 로 적었다. 결과 파일 이름(standoff.md·.json)은 명세·사전 등록 그대로이고, 도구 이름만
작업 지시대로 standoff_r2.py 다(R0 의 chase_r0.py 하네스를 이어받아 넓혔다).

설정: W7 세계 `configs/v3_r2_w7_on.yaml`(시드 SEEDS = 12000~12002 — 판정 시드 12160~12199 가 아니다)를 빌려 개체 0 과 위협 하나만
남긴다(chase_r0.setup 과 같은 하네스): 은신처 없음, 먹이 가득(GRAZE 는 머리 숙여 정지해 먹는다), 개체 0 은 맵 가운데에서 위협
쪽(−x)을 본다, 위협은 −x 쪽 실거리 D0 에서 개체 쪽(+x)을 본다, 나머지 개체는 구석. 낮(d = 0)과 한밤(d = 1, 야행성 잠행형).
위협: 잠행형(배회 상태, 근접 포획 1), 플레이어 대역(잠행 모드), 근접 추격형 ×0.6·×0.95, 원거리형(× 세계 배수 × 0.6, 확률 포획).
위협의 '지난 스텝 이동'(pred_vel)은 R0 하네스처럼 0 에서 시작한다(첫 관측의 접근 관측 0.5 — 첫 스텝의 반응은 거리로만 난다.
그래서 먹다가 시작한 개체는 첫 위협 스텝 전에 노려보기 니치에 들지 않고, D0 ≤ 6 이면 첫 스텝에 돌진이 온다).
잠행 위협(잠행형·플레이어)은 개체 0 을 이미 잠근 채로 시작한다(`pred_lock` = 0 — 나를 향해 기어 오던 위협. 잠금이 없으면 실거리
7.8 밖에서 얼어 있는 개체는 체감 거리 × 1.8 이 시야 14 를 넘어 처음부터 표적이 되지 못한다. 잠금 없음 판(b′)은 이 값이
'지난 스텝 표적' 기록일 뿐이라 다음 스텝 표적 선택에서 바로 지워질 수 있다).
시작 행동 B0: GRAZE(먹다가 시작) 또는 FREEZE(이미 얼어서 위협을 보는 채로 시작).
결정: '잠금 없음' = 시작 잠금 0(첫 결정이 바로 — 그 뒤 들어간 행동에는 세계의 잠금이 걸린다), '잠금 중' = B0 에 막 들어온
상태(잠금 12)이고 B0 에 머무는 동안 하네스가 잠금을 1 이상으로 붙잡아 사건과 결정 지연 0~3 으로만 결정한다(지연마다 따로 잰다 —
멀리서 시작한 시행에서도 잠금이 위협이 보이기 전에 저절로 끝나지 않게. 한 번 다른 행동으로 바뀐 뒤에는 세계의 잠금 그대로).
개체 규칙 (요청은 기본 B0, 한 번 FLEE 를 요청하면 계속 FLEE — chase_r0 과 같다. *_ns·evt* 규칙만 예외):
  (a) rbase: 보이는 위협이 거리 ≤ 4 이거나 접근 ≥ 0.9 면 FLEE (R_base(4, 0.9))
  (b) stare: (a) + X7 니치면 FREEZE (`repertoire_rules.NICHES['stare']`): 보임 & 4 < 거리 ≤ 10 & 0.63 ≤ 접근 < 0.67, 또는 유지 줄
      (지금 FREEZE & 보임 & 4 < 거리 ≤ 10 & 0.45 ≤ 접근 < 0.67 — 멈춘 대치 0.5 에서도 노려보기를 잇는다, 사전 등록 변경 기록
      10-12 (2))
  (c) head±25·head±35·head180: 늘 FREEZE 이고 하네스가 heading 을 위협 방향에서 그 각만큼 돌려 덮는다(제어기 뒤, 위협 스텝 전)
  (d) back2·back4: (b) 인데 위협의 spot_cnt 가 k 에 닿은 다음 스텝에 먹기로 돌아간다(하네스가 잠금을 풀어 결정을 강제한다 —
      FREEZE 잠금 12 가 대치 6 보다 길어 규칙 요청만으로는 대치 중에 돌아갈 수 없다). 돌아간 뒤에는 (a)
  (e) never: 늘 B0 (도망 안 함)
  (f) zflee: (b) 의 노려보기 + 보이는 위협이 거리 ≤ 4 면 계속 FREEZE + 접근 ≥ 0.9 일 때만 FLEE(거리 문턱으로는 뛰지 않는다 —
      '얼었다 뛰기', R0 가까운 위협 앞 얼기). 들킨 돌진이 뛰기보다 느려 얼었다 도망하면 산다는 것(명세 2-3)을 지연별로 본다
  (b′) stare_nolock: (b) 인데 W7 의 target_lock false 판('지난 스텝 표적' 기록만) — 잠금이 없으면 얼자마자 표적을 잃는다
  (b+nb)·(b′+nb) stare_nb·stare_nolock_nb: (b)·(b′) 에 옆 개체 하나(개체 1, 개체 0 의 +y 쪽 NB_OFF, +x 를 보며 늘 먹는다)를
      더한다 — 잠금이 없으면 개체 0 이 얼자마자 표적이 옆 개체로 바뀌고(위험 넘기기), 잠금이 있으면 바뀌지 않는다
  (g) rbase_ns·stare_ns·zflee_ns: (a)·(b)·(f) 의 '끈적이지 않는' 판 — 요청을 스텝마다 다시 정하고 기본은 GRAZE 다(R_base 그대로:
      도망한 뒤 위협이 시야각 밖 등 뒤로 가면 먹기를 요청한다). 실제 세계의 R_base 도망이 들킨 돌진에서 사는지 본다(구현 검토)
  (h) evt2·evt4 (와 비교용 evt2_old·evt4_old): stare_ns 인데 위협의 spot_cnt 가 k 에 닿은 다음 스텝에 하네스가 결정 시점을 하나
      연다(잠금 0 — FREEZE 잠금 중 E1~E6 사건의 대역). 요청은 규칙이 정한다. *_old 는 유지 줄이 없는 옛 X7 정의라 멈춘 대치
      (접근 0.5)에서 먹기를 요청해 대치를 스스로 깬다(구현 검토가 찾은 결함). 유지 줄이 있으면 대치가 물러남까지 간다
끝: 잡힘, 첫 공격이 끝남(잠행형 탈진 시작, 플레이어 휴식 시작), 물러남이 끝남(배회로 돌아옴), 또는 MAX_STEPS.
기록: 잡힘, 대치 수·첫 대치의 실거리, 물러남, 들킴·들킨 돌진, 공격 시작 실거리, 공격 중 가장 좁은 간격(min_gap = 위협 이동 뒤
간격, min_gap_c = 포획 판정 때의 간격 = 초식 이동 뒤·위협 이동 전 — 포획 거리 1.0 과 견줄 값은 min_gap_c 다), 첫 FREEZE·FLEE 스텝.
문턱 일치(골든 제외·경계 골든, 명세 6절): 시작 기하가 세계·규칙 문턱과 정확히 같은 칸(얼어서 시작 D0 = spot_r, 시작 체감 거리 =
돌진 거리, R_base 거리 θ = D0, X7 니치 경계 4·10 = D0, 한밤 먹는 개체의 시야 = D0)은 표에 '‡'를 단다. 비교 연산이 '<=' 라 같으면
참 쪽이고, C++ float 에서 좌표가 정확히 표현되지 않으면 뒤집힐 수 있다. 그런 칸은 D0 ± SHIFT 판을 따로 재 '경계 옮긴 판' 표에
적는다 — 골든은 이 옮긴 판에서 고른다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

CONFIG = "configs/v3_r2_w7_on.yaml"
SEEDS = (12000, 12001, 12002)
D0S = (12.0, 10.0, 8.0, 6.0, 5.0, 4.5, 4.0)
MAX_STEPS = 150
JITTERS = (0, 1, 2, 3)
THREATS = ("stalker", "player", "chaser06", "chaser095", "ranged")
HEADS = {"head+25": 25.0, "head-25": -25.0, "head+35": 35.0, "head-35": -35.0, "head180": 180.0}
BACKS = {"back2": 2, "back4": 4}
EVTS = {"evt2": 2, "evt4": 4, "evt2_old": 2, "evt4_old": 4}
NS_RULES = ("rbase_ns", "stare_ns", "zflee_ns") + tuple(EVTS)       # 끈적이지 않는 요청(기본 GRAZE)
OLD_RULES = ("evt2_old", "evt4_old")     # 유지 줄이 없는 옛 X7 정의(비교용)
FLEE_D, FLEE_A = 4.0, 0.9                # R_base(θ 4, a 0.9)
NB_OFF = 3.0                             # 옆 개체(규칙 *_nb)의 자리: 개체 0 의 +y 쪽 실거리
SHIFT = 0.01                             # 문턱 일치 칸의 경계 옮긴 판(D0 ± SHIFT)


def _rows():
    """(위협, 시작 행동, 규칙, 결정 판, 밤) 목록. 잠금 중 판은 지연마다 따로다."""
    rows = []
    for kind in THREATS:
        rules = ["rbase", "stare", "zflee"]
        for r in rules:
            for b0 in ("graze", "freeze"):
                rows.append((kind, b0, r, "free", False))
                rows += [(kind, b0, r, f"locked{j}", False) for j in JITTERS]
        rows += [(kind, b0, "never", "free", False) for b0 in ("graze", "freeze")]
        if kind in ("stalker", "player"):
            rows += [(kind, "freeze", h, "free", False) for h in HEADS]
            rows += [(kind, b0, k, "free", False) for k in BACKS for b0 in ("graze", "freeze")]
            for r in ("rbase_ns", "stare_ns", "zflee_ns"):
                for b0 in ("graze", "freeze"):
                    rows.append((kind, b0, r, "free", False))
                    rows += [(kind, b0, r, f"locked{j}", False) for j in JITTERS]
            rows += [(kind, b0, k, "free", False) for k in EVTS for b0 in ("graze", "freeze")]
        if kind == "stalker":
            rows += [(kind, b0, "stare_nolock", "free", False) for b0 in ("graze", "freeze")]
            rows += [(kind, b0, r, "free", False) for r in ("stare_nb", "stare_nolock_nb") for b0 in ("graze", "freeze")]
            for r in ("rbase", "stare"):
                rows.append((kind, "graze", r, "free", True))
                rows += [(kind, "graze", r, f"locked{j}", True) for j in JITTERS]
    return rows


def _cfg(nolock: bool):
    from env_v2.config import load_v2_config

    cfg = load_v2_config(ROOT / CONFIG)
    if nolock:
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        f["stare_down"] = dict(f["stare_down"], target_lock=False)
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    return cfg


def setup(cfg, seed: int, kind: str, beh0: int, locked: bool, jitter: int, d0: float, night: bool,
          neighbor: bool = False):
    """chase_r0.setup 과 같은 하네스(위협 하나·개체 0)에 M7 위협별 상태(`World._stare_reset`)와 첫 접근 속도를 더한다."""
    from env_v2 import repertoire as rep
    from env_v2.world import PM_STALK, PT_CHASER, PT_PLAYER, PT_STALKER, World

    class HW(World):
        head_off = None                 # (c) 규칙: 위협 스텝 전에 개체 0 의 heading 을 덮는다(도)

        def _step_predators_v3(self):
            if self.head_off is not None and self._rs.behavior[0] == rep.FREEZE:
                v = self.pred_pos[0] - self.pos[0]
                n = float(np.hypot(v[0], v[1]))
                if n > 0.0:
                    a = math.radians(self.head_off)
                    u = v / n
                    self.head[0] = [u[0] * math.cos(a) - u[1] * math.sin(a), u[0] * math.sin(a) + u[1] * math.cos(a)]
            return super()._step_predators_v3()

    w = HW(cfg, seeds=[seed])
    hs = w.cfg.herb_speed
    if night:                           # 한밤 d = 1 (하루 600, 위상 450 — 120스텝 동안 한밤)
        w.day_fixed = False
        w.dn_period, w.dn_offset = 600, 450
    else:
        w.day_fixed = True
    w._daynight_update()
    w.cov_c, w.cov_r = np.zeros((0, 2)), np.zeros(0)
    w.food[:] = 1.0
    w.food_cap[:] = 1.0
    c = np.array([w.size / 2, w.size / 2])
    w.pos[:] = [0.5, 0.5]
    w.pos[0] = c
    w.head[0] = [-1.0, 0.0]
    if neighbor:                        # 옆 개체: 위협을 등지고(+x) 늘 먹는다
        w.pos[1] = c + [0.0, NB_OFF]
        w.head[1] = [1.0, 0.0]
    player = kind == "player"
    ranged = kind == "ranged"
    w.M, w.M_base = 1, 0 if player else 1
    w.pred_pos = np.array([c + [-d0, 0.0]])
    w.pred_head = np.array([[1.0, 0.0]])
    w.pred_ranged = np.full(1, ranged)
    w._pred_ranged_v1 = np.full(1, ranged)
    mult = {"chaser06": 0.6, "chaser095": 0.95}.get(kind, w.pred_speed_mult)
    sp = hs * mult * (w.cfg.pred_ranged_speed_mult if ranged else 1.0)
    w.pred_speed = np.full(1, sp)
    w.pred_catch_r = np.full(1, w._th["player_catch_r"] if player else
                             (w.cfg.pred_ranged_catch_r if ranged else w.cfg.pred_melee_catch_r))
    w.pred_cd = np.zeros(1, dtype=np.int32)
    w.pred_type = np.array([PT_PLAYER if player else (PT_STALKER if kind == "stalker" else PT_CHASER)], dtype=np.int8)
    w.pred_is_player = w.pred_type == PT_PLAYER
    w.player_present = player
    w.stalk_state = np.zeros(1, dtype=np.int8)
    w.stalk_left = np.zeros(1, dtype=np.int64)
    w.player_mode = np.full(1, PM_STALK, dtype=np.int8)
    w.player_left = np.full(1, 10 ** 6, dtype=np.int64)
    w.pred_nocturnal = np.ones(1, dtype=bool)
    w.pred_asleep = np.zeros(1, dtype=bool)
    w._pred_speed_mult = np.ones(1)
    w._stare_reset()
    if kind in ("stalker", "player"):   # 잠행 위협은 개체 0 을 이미 잠근 채로 시작한다(나를 향해 기어 오던 위협)
        w.pred_lock[0] = 0
    w.pred_vel = np.zeros((1, 2))
    rs, rp = w._rs, w._rp
    # 사건 기준값을 하네스가 만든 지금 상태에 맞춘다: 위협은 '처음 나타난' 것으로(직전에 본 위협 없음 — 보이면 E1), 어둠·
    # 에너지는 지금 값(원래 세계의 reset 값과 달라 첫 스텝에 가짜 E4·E5 가 나지 않게)
    rs.prev_pc[:] = 0
    rs.prev_near[:] = False
    rs.prev_fast[:] = False
    rs.prev_low[:] = w.energy / w.cfg.max_energy < rp["event_energy"]
    rs.prev_dark[:] = w.dark >= rp["event_dark"]
    rs.ev_wait[:] = -1
    rs.behavior[0] = beh0
    rs.lock_left[0] = rp["locks"][beh0] if locked else 0
    rs.jitter[0] = jitter
    see = rp["graze_head_down"] if beh0 == rep.GRAZE else 1.0
    w._rep_see[0] = w._rep_see_last[0] = see
    w._g = w._geometry()
    rep.perceive(rs, rp, w._g)
    w._obs = w._obs_from(w._g)
    return w


def trial(args) -> dict:
    """한 시행 (모듈 docstring 의 규칙·끝·기록)."""
    import repertoire_rules as rr
    from env_v2 import repertoire as rep
    from env_v2.world import PM_CHARGE, PM_REST, ST_BALK, ST_EXHAUST, ST_POUNCE, ST_ROAM, ST_STANDOFF

    kind, b0name, rule, mode, night, seed, d0 = args
    b0 = rep.GRAZE if b0name == "graze" else rep.FREEZE
    locked = mode.startswith("locked")
    jitter = int(mode[6:]) if locked else 0
    nb = rule.endswith("_nb")
    cfg = _cfg(rule.startswith("stare_nolock"))
    w = setup(cfg, seed, kind, b0, locked, jitter, d0, night, neighbor=nb)
    w.head_off = HEADS.get(rule)
    st = rr.NICHES["stare"]
    stares = (rule in ("stare", "stare_nolock", "zflee", "stare_nb", "stare_nolock_nb", "stare_ns", "zflee_ns")
              or rule in BACKS or rule in EVTS)
    flees = (rule in ("rbase", "stare", "stare_nolock", "zflee", "stare_nb", "stare_nolock_nb") or rule in BACKS
             or rule in NS_RULES)
    zf = rule in ("zflee", "zflee_ns")
    flee_d = -1.0 if zf else FLEE_D
    sticky = rule not in NS_RULES
    hold_on = rule not in OLD_RULES
    player = kind == "player"
    flee = back = force = moved = evt_done = False
    out = dict(caught=False, standoff=0, standoff_d=None, balk=False, spotted=False, spotted_charge=False,
               attack_d=None, attack_t=None, break_t=None, min_gap=None, min_gap_c=None, freeze_t=None, flee_t=None,
               lost=False, switched=False, nb_caught=False, steps=MAX_STEPS, end="max")
    prev_state = int(w.stalk_state[0])
    attacking0 = False
    for t in range(MAX_STEPS):
        g = w._g
        seen = g["pred_count"][0] > 0
        d, app = float(g["d_pred_min"][0]), float(g["pred_approach"][0])
        flee_now = flees and seen and (d <= flee_d or app >= FLEE_A)
        flee = (flee or flee_now) if sticky else flee_now
        rng = seen and st["near"] < d <= st["far"]
        niche = rng and st["app_lo"] <= app < st["app_hi"]
        if hold_on and rng and int(w._rs.behavior[0]) == rep.FREEZE and st["hold_lo"] <= app < st["app_hi"]:
            niche = True                    # X7 유지 줄(사전 등록 변경 기록 10-12 (2))
        if zf:
            niche = niche or (seen and d <= st["near"])
        if flee:
            r0 = rep.FLEE
        elif back:
            r0 = rep.GRAZE
        elif stares and niche:
            r0 = rep.FREEZE
        else:
            r0 = b0 if sticky else rep.GRAZE
        if force:
            w._rs.lock_left[0] = 0
            force = False
        elif locked and not moved:          # 잠금 중: B0 에 머무는 동안 잠금이 저절로 끝나지 않는다(사건·지연으로만 결정)
            w._rs.lock_left[0] = max(int(w._rs.lock_left[0]), 1)
        req = np.full((w.N, 1), float(rep.GRAZE))
        req[0, 0] = r0
        _, _, done, _ = w.step(req)
        beh = int(w.behavior[0])
        moved = moved or beh != b0
        if beh == rep.FREEZE and out["freeze_t"] is None:
            out["freeze_t"] = t
        if beh == rep.FLEE and out["flee_t"] is None:
            out["flee_t"] = t
        dd = float(np.linalg.norm(w.pred_pos[0] - w.pos[0]))
        s = int(w.stalk_state[0])
        if s == ST_STANDOFF and prev_state != ST_STANDOFF:
            out["standoff"] += 1
            if out["standoff_d"] is None:
                out["standoff_d"] = round(dd, 2)
        if s == ST_BALK:
            out["balk"] = True
        if prev_state == ST_STANDOFF and s not in (ST_STANDOFF, ST_BALK) and out["break_t"] is None:
            out["break_t"] = t                  # 대치가 물러남 없이 깨진 스텝
        if w.spotted_left[0] > 0:
            out["spotted"] = True
        attacking = (w.player_mode[0] == PM_CHARGE) if player else (s == ST_POUNCE)
        if attacking and not attacking0 and out["attack_d"] is None:
            out["attack_d"] = round(float(np.linalg.norm(w.pred_pos[0] - w.pos[0] - w.pred_vel[0])), 2)
            out["attack_t"] = t
            out["spotted_charge"] = bool(player and w.spotted_charge[0])
        if attacking or attacking0:
            out["min_gap"] = round(dd if out["min_gap"] is None else min(out["min_gap"], dd), 2)
            dc = float(np.linalg.norm(w.pred_pos[0] - w.pos[0] - w.pred_vel[0]))     # 포획 판정 때(위협 이동 전)
            out["min_gap_c"] = round(dc if out["min_gap_c"] is None else min(out["min_gap_c"], dc), 2)
        if nb and w.pred_lock[0] == 1:
            out["switched"] = True              # 표적이 옆 개체로 바뀌었다
        if rule.startswith("stare_nolock") and not out["balk"] and s == ST_ROAM and beh == rep.FREEZE and w.pred_lock[0] < 0:
            out["lost"] = True              # 잠금 없음 판: 얼자마자(체감 거리 × 1.8 > 시야 14) 표적을 잃었다
        if rule in BACKS and not back and w.spot_cnt[0] >= BACKS[rule]:
            back = force = True
        if rule in EVTS and not evt_done and w.spot_cnt[0] >= EVTS[rule]:
            evt_done = force = True             # 다음 스텝에 결정 시점 하나(사건 대역). 요청은 규칙이 정한다
        if done[0]:
            out.update(caught=True, steps=t, end="caught")
            break
        if nb and done[1]:
            out.update(nb_caught=True, steps=t, end="neighbor_caught")
            break
        if (player and w.player_mode[0] == PM_REST) or (not player and s == ST_EXHAUST):
            out.update(steps=t, end="attack_over")
            break
        if prev_state == ST_BALK and s != ST_BALK:
            out.update(steps=t, end="balk_over")
            break
        prev_state = s
        attacking0 = attacking
    return dict(key=(kind, b0name, rule, mode, night), seed=seed, d0=d0, **out)


def _edge_vals():
    """문턱 값(설정에서): spot_r, 돌진 거리(잠행형·플레이어), c_still, R_base θ, X7 니치 경계, 한밤 먹는 개체의 시야 반경."""
    cfg = _cfg(False)
    f = cfg.v2["features"]
    import repertoire_rules as rr

    st = rr.NICHES["stare"]
    rp = f["repertoire"]
    night_see = float(cfg.see_r) * (1.0 - float(f["daynight"]["detect_night"]) * 1.0) * float(rp["graze_head_down"])
    return dict(spot_r=float(f["stare_down"]["spot_r"]), stalk_dist=float(f["threats"]["stalk_dist"]),
                player_charge_dist=float(f["threats"]["player_charge_dist"]), c_still=float(rp["c_still"]),
                near=float(st["near"]), far=float(st["far"]), night_see=night_see)


def edges(row: tuple, d0: float, ev: dict) -> list[str]:
    """시작 기하가 문턱과 정확히 같은 항목(모듈 docstring '문턱 일치'). 같음은 1e-9 안으로 본다(float64 의 끝자리 차를 흡수)."""
    kind, b0, rule, mode, night = row
    eq = lambda a, b: abs(a - b) < 1e-9     # noqa: E731
    out = []
    creep = kind in ("stalker", "player")
    if creep and b0 == "freeze" and eq(d0, ev["spot_r"]):
        out.append("spot_r")
    p0 = d0 * (ev["c_still"] if b0 == "freeze" else 1.0)
    if (kind == "stalker" and eq(p0, ev["stalk_dist"])) or (kind == "player" and eq(p0, ev["player_charge_dist"])):
        out.append("돌진 거리")
    flees = rule not in ("never",) and rule not in HEADS and rule not in ("zflee", "zflee_ns")
    if flees and eq(d0, FLEE_D):
        out.append("θ")
    # X7 니치 경계: 첫 관측의 접근은 0.5 라 니치 띠는 첫 스텝에 닿지 않는다. 유지 줄(지금 FREEZE & 0.45 ≤ 접근)은 얼어서 시작한
    # 개체에 첫 스텝부터 걸리고, 요청이 기본 GRAZE 인 끈적이지 않는 규칙에서만 결과를 바꾼다
    hold = b0 == "freeze" and rule in NS_RULES and rule not in OLD_RULES and rule != "rbase_ns"
    if hold and (eq(d0, ev["near"]) or eq(d0, ev["far"])):
        out.append("니치 경계")
    if night and b0 == "graze" and eq(d0, ev["night_see"]):
        out.append("한밤 시야")
    return out


def _collect(res_list) -> dict:
    out = {}
    for r in res_list:
        kind, b0, rule, mode, night = r["key"]
        key = f"{kind}|{b0}|{rule}|{mode}|{'night' if night else 'day'}|{r['d0']:g}"
        out.setdefault(key, []).append({k: v for k, v in r.items() if k != "key"})
    return out


def table(workers: int) -> tuple[dict, dict]:
    """(표, 경계 옮긴 판). 경계 옮긴 판은 문턱 일치 칸의 D0 ± SHIFT 다."""
    ev = _edge_vals()
    jobs = [r + (s, d0) for r in _rows() for d0 in D0S for s in SEEDS]
    shifted = [r + (s, round(d0 + sg * SHIFT, 6)) for r in _rows() if r[3] == "free" for d0 in D0S if edges(r, d0, ev)
               for sg in (-1, 1) for s in SEEDS]           # 옮긴 판은 '잠금 없음' 행만(잠금 중 행은 같은 기하다)
    if workers <= 1:
        res = [trial(j) for j in jobs + shifted]
    else:
        from env.rollout import _init_worker

        with ProcessPoolExecutor(workers, initializer=_init_worker) as ex:
            res = list(ex.map(trial, jobs + shifted, chunksize=8))
    return _collect(res[:len(jobs)]), _collect(res[len(jobs):])


def _cell(runs) -> str:
    n = len(runs)
    c = sum(r["caught"] for r in runs)
    so = sum(r["standoff"] > 0 for r in runs)
    bk = sum(r["balk"] for r in runs)
    sp = sum(r["spotted"] for r in runs)
    txt = f"{c}/{n}"
    if so:
        ds = [r["standoff_d"] for r in runs if r["standoff_d"] is not None]
        txt += f" 대{so}" + (f"@{np.mean(ds):.1f}" if ds else "")
    if bk:
        txt += f" 물{bk}"
    if sp:
        txt += f" 들{sp}"
    return txt


THREAT_KO = {"stalker": "잠행형", "player": "플레이어 대역", "chaser06": "근접 추격형 ×0.6", "chaser095": "근접 추격형 ×0.95",
             "ranged": "원거리형"}
RULE_KO = {"rbase": "(a) R_base", "stare": "(b) stare + R_base", "never": "(e) 도망 안 함", "stare_nolock": "(b′) stare, 잠금 없음",
           "zflee": "(f) stare + 접근 ≥ 0.9 면 FLEE", "stare_nb": "(b) stare + 옆 개체", "stare_nolock_nb": "(b′) 잠금 없음 + 옆 개체",
           **{h: f"(c) FREEZE heading {HEADS[h]:+g}°" for h in HEADS}, **{k: f"(d) 대치 {v}스텝째 먹기로" for k, v in BACKS.items()},
           "rbase_ns": "(g) R_base, 끈적이지 않음", "stare_ns": "(g) stare + R_base, 끈적이지 않음",
           "zflee_ns": "(g) (f) 끈적이지 않음",
           **{k: f"(h) 대치 {v}스텝째 결정 시점" + (", 옛 X7(유지 줄 없음)" if k in OLD_RULES else "") for k, v in EVTS.items()}}


def highlights(res: dict) -> list[str]:
    """명세 9절 T7 '반드시 보일 것'을 표에서 읽은 값으로 적는다(판정이 아니다 — 읽기 쉬운 요약)."""
    L = []

    def runs(kind, b0, rule, mode="free", night="day", d0=None):
        return [r for d in (D0S if d0 is None else (d0,)) for r in res.get(f"{kind}|{b0}|{rule}|{mode}|{night}|{d:g}", [])]

    for d0 in (12.0, 10.0, 8.0):
        rr_ = runs("stalker", "graze", "stare", d0=d0)
        ds = [r["standoff_d"] for r in rr_ if r["standoff_d"] is not None]
        L.append(f"- 잠행형 × (b), 먹다가 시작, D0 {d0:g}: 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}, 물러남 "
                 f"{sum(r['balk'] for r in rr_)}/{len(rr_)}, 대치 시작 실거리 {sorted(set(ds)) or '없음'}")
    for d0 in (6.0, 5.0, 4.0):
        rr_ = runs("stalker", "graze", "stare", d0=d0)
        L.append(f"- 잠행형 × (b), 먹다가 시작, D0 {d0:g}: 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}, 공격 시작 실거리 "
                 f"{sorted({r['attack_d'] for r in rr_ if r['attack_d'] is not None}) or '없음'}")
    for rule in ("stare", "never"):
        rr_ = runs("stalker", "freeze", rule)
        L.append(f"- 잠행형 × 얼어서 시작 × {RULE_KO[rule]}: 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}, 대치 "
                 f"{sum(r['standoff'] > 0 for r in rr_)}/{len(rr_)}, 물러남 {sum(r['balk'] for r in rr_)}/{len(rr_)}")
    for mode in ("free", "locked0", "locked1", "locked3"):
        rr_ = runs("stalker", "graze", "stare", mode=mode, night="night")
        L.append(f"- 한밤 잠행형 × (b), 먹다가 시작, {mode}: 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}, 대치 "
                 f"{sum(r['standoff'] > 0 for r in rr_)}/{len(rr_)}")
    for h in HEADS:
        rr_ = runs("stalker", "freeze", h)
        L.append(f"- 잠행형 × {RULE_KO[h]}: 대치 {sum(r['standoff'] > 0 for r in rr_)}/{len(rr_)}, 잡힘 "
                 f"{sum(r['caught'] for r in rr_)}/{len(rr_)}, 공격 시작 실거리 "
                 f"{sorted({r['attack_d'] for r in rr_ if r['attack_d'] is not None}) or '없음'}")
    for k in BACKS:
        for d0s, lab in (((6.0, 5.0, 4.5), "실거리 ≤ 6"), ((12.0, 10.0, 8.0), "실거리 > 6")):
            rr_ = [r for d0 in d0s for r in runs("stalker", "freeze", k, d0=d0)]
            br = [r for r in rr_ if r["break_t"] is not None]
            now = sum(r["attack_t"] == r["break_t"] for r in br)
            L.append(f"- 잠행형 × 얼어서 시작 × {RULE_KO[k]}, D0 {'·'.join(f'{d:g}' for d in d0s)}({lab}에서 깨짐): 깨짐 "
                     f"{len(br)}/{len(rr_)}, 깨진 그 스텝에 돌진 {now}/{len(br)}, 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}")
    for kind in ("chaser06", "chaser095", "ranged"):
        rr_ = [r for key, v in res.items() if key.startswith(kind + "|") for r in v]
        L.append(f"- {THREAT_KO[kind]} × 모든 규칙: 대치 {sum(r['standoff'] > 0 for r in rr_)}/{len(rr_)}")
    for d0s, lab in (((12.0, 10.0, 8.0), "D0 > 6"),):
        rr_ = [r for d0 in d0s for m in ["free"] + [f"locked{j}" for j in JITTERS]
               for r in runs("player", "graze", "stare", mode=m, d0=d0)]
        gaps = [r["min_gap"] for r in rr_ if r["spotted_charge"] and r["min_gap"] is not None]
        gapc = [r["min_gap_c"] for r in rr_ if r["spotted_charge"] and r["min_gap_c"] is not None]
        L.append(f"- 플레이어 × (b), 먹다가 시작, {lab}(잠금 없음·지연 0~3): 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}, "
                 f"들킴 {sum(r['spotted'] for r in rr_)}/{len(rr_)}, 들킨 돌진 {sum(r['spotted_charge'] for r in rr_)}/{len(rr_)}, "
                 f"들킨 돌진의 가장 좁은 간격 최소 {min(gaps) if gaps else '—'}(위협 이동 뒤) · "
                 f"{min(gapc) if gapc else '—'}(포획 판정 때, 포획 거리 1.0 과 견준다)")
    for rule in ("stare", "zflee"):
        for d0 in (6.0, 5.0, 4.5, 4.0):
            rr_ = runs("player", "freeze", rule, d0=d0)
            L.append(f"- 플레이어 × 얼어서 시작 × {RULE_KO[rule]}, D0 {d0:g}: 들킴 {sum(r['spotted'] for r in rr_)}/{len(rr_)}, "
                     f"들킨 돌진 {sum(r['spotted_charge'] for r in rr_)}/{len(rr_)}, 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}")
    for b0 in ("graze", "freeze"):
        rr_ = [r for d0 in (12.0, 10.0, 8.0, 6.0, 5.0, 4.5) for m in ["free"] + [f"locked{j}" for j in JITTERS]
               for r in runs("player", b0, "zflee", mode=m, d0=d0)]
        sc = [r for r in rr_ if r["spotted_charge"]]
        gaps = [r["min_gap"] for r in sc if r["min_gap"] is not None]
        gapc = [r["min_gap_c"] for r in sc if r["min_gap_c"] is not None]
        L.append(f"- 플레이어 × {b0} 시작 × {RULE_KO['zflee']}(D0 ≥ 4.5, 잠금 없음·지연 0~3): 들킨 돌진 {len(sc)}/{len(rr_)}, 그중 잡힘 "
                 f"{sum(r['caught'] for r in sc)}, 들킨 돌진의 가장 좁은 간격 최소 {min(gaps) if gaps else '—'}(이동 뒤) · "
                 f"{min(gapc) if gapc else '—'}(포획 판정 때), 들키지 않은 돌진 "
                 f"{sum(r['attack_d'] is not None and not r['spotted_charge'] for r in rr_)}, 그중 잡힘 "
                 f"{sum(r['caught'] for r in rr_ if r['attack_d'] is not None and not r['spotted_charge'])}")
    for kind in ("player", "stalker"):        # (g) 끈적이지 않는 도망(실제 R_base): 들킨 돌진이 도망하는 개체를 지켜 주는가
        for rule in ("rbase_ns", "stare_ns", "zflee_ns"):
            for b0 in ("graze", "freeze"):
                rr_ = [r for d0 in (12.0, 10.0, 8.0, 6.0, 5.0, 4.5) for m in ["free"] + [f"locked{j}" for j in JITTERS]
                       for r in runs(kind, b0, rule, mode=m, d0=d0)]
                sc = [r for r in rr_ if r["spotted_charge"]]
                un = [r for r in rr_ if r["attack_d"] is not None and not r["spotted_charge"]]
                L.append(f"- {THREAT_KO[kind]} × {b0} 시작 × {RULE_KO[rule]}(D0 ≥ 4.5, 잠금 없음·지연 0~3): 잡힘 "
                         f"{sum(r['caught'] for r in rr_)}/{len(rr_)}, 대치 {sum(r['standoff'] > 0 for r in rr_)}, 물러남 "
                         f"{sum(r['balk'] for r in rr_)}, 들킨 돌진 {len(sc)}(그중 잡힘 {sum(r['caught'] for r in sc)}), 들키지 않은 "
                         f"공격 {len(un)}(그중 잡힘 {sum(r['caught'] for r in un)})")
    for b0 in ("graze", "freeze"):            # (h) 대치 중 결정 시점: 유지 줄이 있으면 대치를 잇고, 옛 정의는 스스로 깬다
        for k in EVTS:
            rr_ = runs("stalker", b0, k)
            br = [r for r in rr_ if r["break_t"] is not None]
            L.append(f"- 잠행형 × {b0} 시작 × {RULE_KO[k]}: 대치 {sum(r['standoff'] > 0 for r in rr_)}/{len(rr_)}, 물러남 "
                     f"{sum(r['balk'] for r in rr_)}/{len(rr_)}, 깨짐 {len(br)}/{len(rr_)}(그 스텝에 돌진 "
                     f"{sum(r['attack_t'] == r['break_t'] for r in br)}), 잡힘 {sum(r['caught'] for r in rr_)}/{len(rr_)}")
    for b0 in ("graze", "freeze"):
        a = runs("stalker", b0, "stare_nb")
        b = runs("stalker", b0, "stare_nolock_nb")
        L.append(f"- 잠행형 × {b0} 시작 × 옆 개체(실거리 {NB_OFF:g}, 늘 먹기), 잠금 있음 대 없음: 개체 0 과 대치 "
                 f"{sum(r['standoff'] > 0 for r in a)}/{len(a)} 대 {sum(r['standoff'] > 0 for r in b)}/{len(b)}, 표적이 옆 개체로 바뀜 "
                 f"{sum(r['switched'] for r in a)} 대 {sum(r['switched'] for r in b)}, 옆 개체 잡힘 {sum(r['nb_caught'] for r in a)} 대 "
                 f"{sum(r['nb_caught'] for r in b)}, 개체 0 잡힘 {sum(r['caught'] for r in a)} 대 {sum(r['caught'] for r in b)}")
    for b0 in ("graze", "freeze"):
        a = runs("stalker", b0, "stare")
        b = runs("stalker", b0, "stare_nolock")
        L.append(f"- 잠행형 × (b) {b0} 시작, 잠금 있음 대 없음: 대치 {sum(r['standoff'] > 0 for r in a)}/{len(a)} 대 "
                 f"{sum(r['standoff'] > 0 for r in b)}/{len(b)}, 잡힘 {sum(r['caught'] for r in a)} 대 "
                 f"{sum(r['caught'] for r in b)}, 잠금 없음 판에서 얼자마자 표적을 잃음 {sum(r['lost'] for r in b)}/{len(b)}")
    return L


def summary_md(res: dict, cfg, shifted: dict | None = None) -> str:
    sd = cfg.v2["features"]["stare_down"]
    th = cfg.v2["features"]["threats"]
    L = ["# v3 R2 결정적 확인표 T7 — 노려보기 대치 (M7)", "",
         f"설정 {CONFIG}: spot_r {sd['spot_r']}, spot_cos {sd['spot_cos']}, spot_steps {sd['spot_steps']}, 물러남 "
         f"{sd['balk_steps']}스텝 ×{sd['balk_speed']}, 들킴 {sd['spotted_steps']}스텝·들킨 돌진 ×{sd['spotted_charge_speed']}. "
         f"잠행 ×{th['stalk_speed']}·돌진 거리 {th['stalk_dist']}, 플레이어 잠행 ×{th['player_speeds'][1]}·돌진 "
         f"×{th['player_speeds'][2]}. 세계 시드 {list(SEEDS)}(판정 시드 아님). 은신처 없음, 먹이 가득. 판정이 아니다.", "",
         "칸 = 잡힌 수 / 시행 수, '대k@x' = 대치가 생긴 시행 k(첫 대치 실거리 평균 x), '물k' = 물러남 k, '들k' = 플레이어 들킴 k. "
         "'잠금 없음'은 첫 결정이 바로(그 뒤 들어간 행동은 세계의 잠금), 'locked j' 는 B0 잠금 12 에서 사건·지연 j 로만 결정. "
         "'‡' = 문턱 일치 칸(시작 기하가 문턱과 정확히 같다 — 골든에서 빼고, 아래 '경계 옮긴 판'에서 D0 ± "
         f"{SHIFT:g} 로 다시 잰다, 명세 6절). X7 니치는 유지 줄을 포함한다(사전 등록 변경 기록 10-12 (2)).", "",
         "## 반드시 보일 것 (명세 9절 T7) — 표에서 읽은 값", "",
         "명세 9절 T7 문구의 정오표(사전 등록 변경 기록 10-12 (2)): '잠행형 × 얼어서 시작: D0 > 3.33이면 첫 스텝에 대치'는 "
         "min(spot_r 10, 시야) 안에서만 첫 스텝 대치다(D0 12 는 다가온 뒤 9.8 에서, D0 4 는 (b) 가 거리 ≤ 4 에서 먼저 도망한다). "
         "'플레이어 × 얼어서 시작: D0 ≥ 4.5 면 들킴'은 R_base θ 4 때문에 (b) 에서는 D0 4.5 가 경계이고 (f) 로 확인한다. "
         "'가장 좁은 간격'은 위협 이동 뒤 간격이고, 포획 거리와 견줄 값은 포획 판정 때 간격이다.", ""]
    L += highlights(res)
    ev = _edge_vals()
    for kind in THREATS:
        L += ["", f"## {THREAT_KO[kind]}", "",
              "| 시작 | 규칙 | 결정 | 낮밤 | " + " | ".join(f"D0 {d:g}" for d in D0S) + " |",
              "|---" * (4 + len(D0S)) + "|"]
        for (k, b0, rule, mode, night) in _rows():
            if k != kind:
                continue
            nt = "night" if night else "day"
            row = (k, b0, rule, mode, night)
            cells = [_cell(res[f"{k}|{b0}|{rule}|{mode}|{nt}|{d:g}"]) + (" ‡" if edges(row, d, ev) else "") for d in D0S]
            L.append(f"| {'GRAZE' if b0 == 'graze' else 'FREEZE'} | {RULE_KO[rule]} | "
                     f"{'잠금 없음' if mode == 'free' else 'locked ' + mode[6:]} | {'한밤' if night else '낮'} | "
                     + " | ".join(cells) + " |")
    if shifted:
        L += ["", "## 경계 옮긴 판 (문턱 일치 칸의 D0 ± " + f"{SHIFT:g}" + ", 골든 후보)", "",
              "| 위협 | 시작 | 규칙 | 결정 | 낮밤 | 문턱 | D0 − | D0 (‡) | D0 + |", "|---|---|---|---|---|---|---|---|---|"]
        n_edge = 0
        for row in _rows():
            k, b0, rule, mode, night = row
            nt = "night" if night else "day"
            if mode != "free":
                continue
            for d in D0S:
                e = edges(row, d, ev)
                if not e:
                    continue
                n_edge += 1
                lo, hi = round(d - SHIFT, 6), round(d + SHIFT, 6)
                L.append(f"| {THREAT_KO[k]} | {'GRAZE' if b0 == 'graze' else 'FREEZE'} | {RULE_KO[rule]} | "
                         f"{'잠금 없음' if mode == 'free' else 'locked ' + mode[6:]} | {'한밤' if night else '낮'} | "
                         f"{'·'.join(e)} = {d:g} | {_cell(shifted[f'{k}|{b0}|{rule}|{mode}|{nt}|{lo:g}'])} | "
                         f"{_cell(res[f'{k}|{b0}|{rule}|{mode}|{nt}|{d:g}'])} | {_cell(shifted[f'{k}|{b0}|{rule}|{mode}|{nt}|{hi:g}'])} |")
        L += ["", f"'잠금 없음' 행의 문턱 일치 칸 {n_edge}개(시드 {len(SEEDS)}개씩, 잠금 중 행은 같은 기하라 옮긴 판을 따로 재지 않는다)."
              " 골든은 '‡' 칸을 빼고 옮긴 판에서 고른다."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="v3 R2 결정적 확인표 T7(노려보기 대치)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    res, shifted = table(a.workers)
    out = HERE.parent
    ev = _edge_vals()
    edge_cells = sorted({f"{k}|{b0}|{rule}|{mode}|{'night' if night else 'day'}|{d:g}"
                         for (k, b0, rule, mode, night) in _rows() for d in D0S if edges((k, b0, rule, mode, night), d, ev)})
    (out / "standoff.json").write_text(json.dumps(dict(config=CONFIG, seeds=list(SEEDS), d0=list(D0S), max_steps=MAX_STEPS,
                                                       shift=SHIFT, table=res, edge_cells=edge_cells, shifted=shifted),
                                                  separators=(",", ":")), encoding="utf-8")
    md = summary_md(res, _cfg(False), shifted)
    (out / "standoff.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
