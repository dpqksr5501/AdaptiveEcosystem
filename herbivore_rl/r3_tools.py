"""v3 R3 관문·판정 도구가 함께 쓰는 것 (사전 등록 `results/v3/r3/PREREG.md` 2·9-2·15-2절). torch 를 싣지 않는다.

- 시드 규칙(`seed_problems`): 쓰지 않는 범위(2절 표 '쓰지 않음'과 R2·레벨 복제 예약), 관문 판정 15000~15039·최종 판정 10300~10319
  (사전 등록 폴더 실행만), 그 밖에 쓸 수 있는 보정 20000~20019·탐색 32000~32099·33000~33099.
- 사전 등록 초안 판정(`prereg_draft`, eval_v3.prereg_draft 와 같은 규칙 — 제목 줄에 '초안'이 있으면 참).
- R3 세계 판별(`is_r3_world`, World._r3 와 같은 조건을 설정만으로 본다).
- 관문 결과 → 교사·판정 설정(`gate_setup`, 9-2 표): `results/v3/r3/gate/final.json`(invasion_r3.py report 가 쓴다)과 거주 탐색
  `gate/search.json`. 판정 U·FSM_R3 줄·P3·HIDE 사용 하한이 어느 관문에 걸리는지 여기서 한 번 정한다.
- 쫓는 위협 추적(`pursuit_world_class`): 포기율 A 의 '쫓는 위협'(15-2, 재학습 전 측정 `pre/PREREG.md` 2절 4 그대로) — 지난 두 포식자
  스텝 가운데 하나에서 이 사슴을 표적으로 삼았고 지금 깨어 있는 위협. 표적은 세계 훅 `pred_target`이고, 표적이 안 보여도 곧장 이어 가는
  돌진(잠행형 돌진·플레이어 돌진)은 지난 표적을 쫓는 중으로 둔다. `results/v3/r3/pre/eval_pre.py` 의 Spy 와 같은 값을 낸다(시험이
  본다). 기록만 하고 상태·난수를 바꾸지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
GATE_DIR = ROOT / "results" / "v3" / "r3" / "gate"
GATE_B_DIR = ROOT / "results" / "v3" / "r3" / "gate_b"
CONFIG_R3 = "configs/v3_r3_on.yaml"

# 시드 (사전 등록 2절, 명세 11절)
NEVER = (range(10000, 10020), range(10100, 10120), range(10200, 10220), range(12000, 12240), range(14000, 14040),
         range(30000, 30024), range(31000, 31306), range(41000, 41040), range(42000, 42010))
GATE_JUDGE = range(15000, 15040)          # 관문 판정(묶음 A·B, 보정 회차, 무리 확인) — 관문 사전 등록 폴더 실행만
FINAL_JUDGE = range(10300, 10320)         # 최종 판정 — 판정 사전 등록 폴더 실행만
FREE = (range(20000, 20020), range(32000, 32100), range(33000, 33100))
PURSUE_R = 10.0                           # '쫓는 위협이 실거리 10 안'(15-2)
ABANDON = ("graze", "sleep")              # 포기 = GRAZE(SLEEP 을 열었으면 SLEEP 도). 원래 R1b 를 볼 때만 FREEZE 도(abandon_ids)


def seed_problems(seeds, *, gate: bool = False, final: bool = False) -> list[str]:
    """시드 목록의 문제(비면 문제 없음). 쓰지 않는 범위는 늘 거부한다. 관문 판정 시드는 `gate`, 최종 판정 시드는 `final` 일 때만 받는다
    (사전 등록 폴더 실행). 그 밖의 시드는 보정·탐색 범위 안이어야 한다."""
    bad = []
    for s in seeds:
        s = int(s)
        if any(s in r for r in NEVER):
            bad.append(f"{s}(쓰지 않는 범위)")
        elif s in GATE_JUDGE:
            if not gate:
                bad.append(f"{s}(관문 판정 시드 15000~15039 — 관문 사전 등록 폴더 실행만)")
        elif s in FINAL_JUDGE:
            if not final:
                bad.append(f"{s}(최종 판정 시드 10300~10319 — 판정 사전 등록 폴더 실행만)")
        elif not any(s in r for r in FREE):
            bad.append(f"{s}(보정 20000~20019·탐색 32000~32099·33000~33099 밖)")
    return bad


def prereg_draft(path) -> bool:
    """사전 등록 파일의 제목 줄(첫 '# ' 줄)에 '초안'이 있으면 참. 파일이 없거나 제목이 없어도 참(받지 않는다)."""
    p = Path(path)
    if not p.exists():
        return True
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return "초안" in line
    return True


def is_r3_world(cfg) -> bool:
    """R3 규칙(추격 고정·지형·늑대 은신처 진입 금지·은신처 먹이 배수 뽑기) 가운데 하나라도 켠 세계인가 — World._r3 와 같은 조건."""
    f = (getattr(cfg, "v2", None) or {}).get("features") or {}

    def on(name):
        return bool((f.get(name) or {}).get("enabled"))
    shel, food = f.get("realism_shelter") or {}, f.get("realism_cover_food") or {}
    return (on("realism_chase") or on("realism_terrain") or (on("realism_shelter") and bool(shel.get("block_predators")))
            or (on("realism_cover_food") and food.get("frac_range") is not None))


# --------------------------------------------------------------------- #
# 관문 결과 → 교사·판정 설정 (사전 등록 9-2 표)
# --------------------------------------------------------------------- #

FSM_GATES = ("crouch", "leave", "run", "keep", "early")      # repertoire_rules.FSM_R3_LINES 와 같다(시험이 본다)
U_GATES = {"keep": "keep", "run": "run", "leave": "leave", "hide": "crouch", "early": "early"}
IN_LINE = ("pass", "conditional_pass")                     # FSM_R3 줄에 넣는 관문 결과(통과·조건부 통과)


def setup_from_final(final: dict | None, search: dict | None) -> dict:
    """관문 최종 결과(`final.json`)와 거주 탐색(`search.json`) → 교사·판정 설정. 9-2 표:
    - FSM_R3 줄: 통과·조건부 통과한 관문(crouch·leave·run·keep·early). 보정 1 을 쓴 관문은 보정 뒤 정의.
    - 판정 U: 완전히 통과한 니치의 U 만 판정(`u_judged`). 조건부 통과·판정 불가·실패는 보고만(`u_report`). U_ESC 는 늘 판정.
    - P3(포기율 A): G1(keep)이 통과 또는 조건부 통과일 때만 판정 조건. HIDE 사용 하한: G2(run)·G4a(crouch) 가운데 하나가 통과(조건부 포함).
    - SLEEP: 묶음 B 의 G5(sleep_r3)가 통과(조건부 아님)하고 G0b-S(camp_sleep)가 '손해 확인'일 때만 연다.
    `complete` 는 두 파일이 다 있을 때만 참이다(아니면 관문 전 — 교사·판정 폴더 실행을 받지 않는다)."""
    out = dict(complete=False, theta=None, approach=None, verdicts={}, cal=(), lines=(), sleep=False,
               u_judged=("esc",), u_report=tuple(U_GATES), p3=False, hide_floor=False)
    if search is not None:
        out["theta"], out["approach"] = float(search["best"]["theta"]), float(search["best"]["approach"])
    if final is None:
        return out
    v = {x: r.get("verdict") for x, r in (final.get("gates") or {}).items()}
    cal = tuple(x for x in FSM_GATES if (final.get("gates") or {}).get(x, {}).get("cal", 0) == 1)
    lines = tuple(x for x in FSM_GATES if v.get(x) in IN_LINE)
    judged = ("esc",) + tuple(u for u, g in U_GATES.items() if v.get(g) == "pass")
    sleep = v.get("sleep_r3") == "pass" and v.get("camp_sleep") == "exploit_loss"
    out.update(complete=search is not None, verdicts=v, cal=tuple(x for x in cal if x in lines), lines=lines, sleep=bool(sleep),
               u_judged=judged, u_report=tuple(u for u in U_GATES if u not in judged),
               p3=v.get("keep") in IN_LINE, hide_floor=v.get("run") in IN_LINE or v.get("crouch") in IN_LINE)
    return out


def gate_setup(gate_dir=None) -> dict:
    """`gate_dir`(기본 results/v3/r3/gate)의 final.json·search.json 으로 `setup_from_final`. 없는 파일은 None 으로 본다."""
    d = Path(gate_dir) if gate_dir is not None else GATE_DIR
    rd = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else None      # noqa: E731
    out = setup_from_final(rd(d / "final.json"), rd(d / "search.json"))
    out["source"] = str(d)
    return out


# --------------------------------------------------------------------- #
# 쫓는 위협 추적 (포기율 A)
# --------------------------------------------------------------------- #

_PURSUIT = None


def pursuit_world_class():
    """World 하위 클래스(한 번 만들어 둔다). 포식자 스텝마다 위협별 쫓은 표적 `pur_tgt`(M,)과 지난 두 스텝의 값 tp1·tp2 를 남긴다.
    표적 = 세계 훅 `pred_target`(현실성·R3 세계에만 있다), 표적이 없는데 잠행형 돌진·플레이어 돌진 중이면 지난 표적. 기록만 한다."""
    global _PURSUIT
    if _PURSUIT is None:
        _PURSUIT = _make_pursuit()
    return _PURSUIT


def _make_pursuit():
    from env_v2.world import PM_CHARGE, PT_STALKER, ST_POUNCE, World

    class PursuitWorld(World):
        def reset(self):
            obs = super().reset()
            if not (self._rz or self._r3):
                raise ValueError("쫓는 위협 추적은 세계 훅 pred_target 이 있는 현실성·R3 세계에서만 쓴다")
            self.pur_prev = np.full(self.M, -1, dtype=np.int64)
            self.tp1 = np.full(self.M, -1, dtype=np.int64)
            self.tp2 = np.full(self.M, -1, dtype=np.int64)
            self._pur_mo = None
            return obs

        def _threat_motion(self, move, speed, wander, has_target, d_t, exh0, rest0):
            out = super()._threat_motion(move, speed, wander, has_target, d_t, exh0, rest0)
            self._pur_mo = (np.asarray(has_target, dtype=bool).copy(), self.stalk_state.copy(), self.player_mode.copy())
            return out

        def _step_predators_v3(self):
            self._pur_mo = None
            caught = super()._step_predators_v3()
            M = self.M
            if self._pur_mo is None:
                tgt = np.full(M, -1, dtype=np.int64)
            else:
                has, st1, pm1 = self._pur_mo
                carry = ~has & (((self.pred_type == PT_STALKER) & (st1 == ST_POUNCE)) | (self.pred_is_player & (pm1 == PM_CHARGE)))
                tgt = np.where(carry, self.pur_prev, self.pred_target).astype(np.int64)
            self.pur_prev = tgt.copy()
            self.tp2, self.tp1 = self.tp1, tgt
            return caught

        def pursuer_dist(self) -> np.ndarray:
            """(N,) 사슴마다 '쫓는 위협'(tp1·tp2 의 표적이 이 사슴이고 지금 깨어 있는 위협)의 지금 실거리 가운데 가장 작은 값(없으면 inf).
            결정 직전(정책을 부르기 전)에 부른다 — eval_pre.py 의 purs_now 와 같다."""
            awake = ~self.pred_asleep if self._ps is not None else np.ones(self.M, dtype=bool)
            purs = np.full(self.N, np.inf)
            for tg in (self.tp1, self.tp2):
                ms = np.flatnonzero((tg >= 0) & awake)
                if len(ms):
                    dd = np.sqrt(((self.pred_pos[ms] - self.pos[tg[ms]]) ** 2).sum(1))
                    np.minimum.at(purs, tg[ms], dd)
            return purs

    return PursuitWorld


def abandon_ids(freeze: bool = False) -> tuple[int, ...]:
    """포기로 세는 행동 번호: GRAZE·SLEEP(원래 R1b 를 볼 때만 FREEZE 도)."""
    from env_v2.repertoire import BEHAVIOR_NAMES

    names = ABANDON + (("freeze",) if freeze else ())
    return tuple(BEHAVIOR_NAMES.index(b) for b in names)


def opportunities(w, pk: dict) -> np.ndarray:
    """포기율 A 의 기회 (N,) bool (15-2): 결정 시점(rep_peek reads) & 지금 행동 FLEE & 쫓는 위협 실거리 < 10 & 은신처 원 밖.
    정책을 부르기 전(w.observe 와 같은 때) 부른다."""
    from env_v2.repertoire import FLEE

    purs = w.pursuer_dist()
    return (np.asarray(pk["reads"], dtype=bool) & (np.asarray(pk["behavior"]) == FLEE) & (purs < PURSUE_R)
            & ~w._in_cover(w.pos))


def terrain_now(w) -> np.ndarray:
    """(N,) 지금 사슴 위치 셀의 땅(0 보통, 1 눈, 2 거친 땅, 3 지형 없는 세계)."""
    if getattr(w, "_zt", None) is None:
        return np.full(w.N, 3, dtype=np.int64)
    return w._rz_terrain_of(w.pos).astype(np.int64)
