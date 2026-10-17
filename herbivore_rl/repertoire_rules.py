"""v3 R0 손 규칙 — 행동 레퍼토리 세계(`features.repertoire`)의 규칙 정책 (명세 RL_V3_R0_SPEC.md 4절, 사전 등록
`results/v3/r0/PREREG.md` 2·3절).

`env_v2/rollout.py` 의 "모듈:함수" 래퍼 문법으로 쓴다(`{"factory": "repertoire_rules:base_rule", ...}`). 바탕 정책은
`{"kind": "fixed", "action": [0.0]}`(늘 GRAZE 요청)이고 규칙 래퍼가 요청을 덮는다. 스펙은 `rule_spec` 이 만든다.
규칙은 관측만 본다(언리얼 규칙 두뇌와 같은 입력). 관측 칸은 이름으로 찾고, 접근 속력(pred_approach)이 필요하므로
repertoire.obs_extra 를 켠 설정에서만 쓴다(`with_obs_extra` — 관측만 늘고 세계 동역학은 같다).

- 기본 규칙 R_base(θ, a) (`base_rule`): 위협이 보이고(관측 1 > 0) 가장 가까운 위협의 거리 ≤ θ 이거나 접근 관측 ≥ a 면
  FLEE, 아니면 GRAZE. 낮밤 모두 같은 문턱이다 — SLEEP 시험의 거주 규칙도 이것이다(밤에도 같은 문턱으로 계속 먹기. 거주
  규칙은 X 를 쓰지 않아야 하므로 밤 잠 선택지는 두지 않는다, PREREG 2절·변경 기록 10-07).
- 행동 X 규칙 (`x_rule`): 바탕 규칙의 요청 위에 X 를 덮는다. `slots` 를 주면 그 슬롯(침입 소수)에만 건다. `mode` 는
  niche(그 행동의 니치), out(니치 밖 — 지배 검사), cross(대안의 니치 — 교차 검사). 조건은 `NICHES` 표(PREREG 3절)다.
  FREEZE·HIDE 의 cross 는 PREREG 의 '도망 대신'대로 바탕 규칙이 FLEE 를 고른 개체에만 건다(대안 = FLEE).
  SLEEP 은 세 모드 모두 바탕 규칙이 FLEE 를 고른 개체에는 걸지 않는다(위협이 가까우면 깨어서 뛴다. 대안 = 밤에 조금 먹기).
  x = graze 는 FLEE 확인용(보고만)이다: 바탕 규칙이 FLEE 를 고르면 대신 GRAZE.
판정 구간: 밤 = 어둠 d ≥ 0.8, 낮 = d ≤ 0.2 (관측 visibility 로 나눈다, `world.daynight_seg_edges`). 거리는 관측 × see_r,
은신처 거리는 관측 6 × obs_cover_norm(가장자리까지, 0 = 은신처 안).

v3 R2 (명세 RL_V3_R2_SPEC.md 4절, 사전 등록 results/v3/r2/PREREG.md 3절): x = stare(X7, G7 — 나를 향해 잠행 속력으로 기어 오는
위협 앞에서 얼어 노려보기)와 look(X8, G8 — 위협은 못 봤지만 강한 경보를 들었을 때 고개 들기 = 얼기)을 더한다. 둘 다 행동은
FREEZE 이고, R0 의 니치·니치 밖처럼 바탕 규칙의 요청과 무관하게 조건만 본다(G7·G8 의 니치·교차는 거주 R_base(θ 4, a 0.9)라면
GRAZE 인 상황이다. 거주 탐색이 θ > 4 를 고르더라도 조건만 본다 — 사전 등록 변경 기록 10-12 (2)). look 은 관측 alarm_heard 가
있는 설정(기능 alarm)에서만 쓴다 — 그 설정에서만 `_geom` 이 alarm_heard·threat_recency 칸을 더 찾는다(다른 설정의 규칙 스펙은
그대로다). `fsm_r2_spec` 은 언리얼 규칙 두뇌 대조군 FSM_R2 다 — 기본값은 노려보기를 뺀 R2 세계(10-13 사람 결정)의 판이고(stare 줄
없음), stare 줄을 넣은 판은 `stare=True` 로 앞선 실행을 재현할 때만 쓴다. stare 규칙(X7)과 보조 규칙은 W7 관문 기록 재현용으로 남긴다.
stare 니치의 유지 줄(사전 등록 변경 기록 10-12 (2)): 지금 FREEZE(관측 beh_freeze)이고 보이는 위협이 4 < 거리 ≤ 10 & 0.45 ≤
접근 < 0.67 이면 FREEZE 를 이어 간다. 대치(M7)에 들어간 잠행형은 멈춰 서서 접근 관측이 0.5 가 되는데, 유지 줄이 없으면 FREEZE
잠금 중 사건(E1~E6)이 연 결정 시점에 규칙이 먹기를 요청해 스스로 대치를 깼다(구현 검토). 물러남(접근 0.2)이나 빠른 위협
(≥ 0.67)이면 유지하지 않는다. 그래서 stare 래퍼 스펙만 beh_freeze 칸 번호를 더 갖는다(`_stare_geo` — 다른 규칙의 스펙은 그대로다).

v3 R3 (명세 RL_V3_R3_SPEC.md 7·8절, 사전 등록 results/v3/r3/PREREG.md 4·5·12절 — 얼기가 없는 세계): R0·R2 규칙과 따로 둔
R3 규칙 묶음이다(`R3_X`, 래퍼 `r3_rule`, 스펙 `r3_wrap`·`r3_rule_spec`, 교사 `fsm_r3_spec`). R0·R2 규칙의 스펙과 결과는 그대로다
(시험이 바꾸기 전 커밋 f6e8b6e 의 이 파일과 견준다). 다른 점은 셋이다.
- 관측 칸 둘(threat_recency, beh_flee)을 더 읽는다(`r3_geo` — R3 래퍼 스펙에만 넣는다). 기호는 사전 등록 5-1: s = 감지, d = 거리,
  a = 접근, c = 은신처 거리(0 이면 원 안), E = 에너지, K = s ∨ threat_recency ≥ 0.2, F = 지금 FLEE(beh_flee).
- 고를 수 있는 자리에서만 X 를 요청한다(사전 등록 4절 '새 규칙'): 그 개체의 지금 관측으로 계산한 가능 칸(`env_v2.rep_policy.
  feasible_mask`, 판 2 — 학습 마스크와 같은 함수)과 허용 목록이 X 를 허용할 때만 덮고, 아니면 바탕 요청을 그대로 둔다. 묶음 B(SLEEP
  을 연 판 4)는 SLEEP 가능 = ¬K 를 더한다(`sleep_v4`).
- 한 규칙이 개체마다 다른 행동을 낼 수 있다: keep_hide(G1-H)는 c < 15 면 HIDE, 아니면 FLEE, camp_sleep(G0b-S)은 K 면 HIDE, 아니면
  SLEEP 이다. 그래서 R3 래퍼는 (덮을 개체, 행동)을 함께 낸다(`R3Rule.target`).
보정 1(사전 등록 9절, 니치를 좁히기만 한다)은 `cal=1` 이다. 보정이 있는 관문은 keep·run·leave·early(·keep_hide 는 keep 의 니치를
따른다)뿐이다.
문턱 비교는 R0·R2 규칙과 같이 float32 관측을 float64 로 바꾸고 단위(× 20)를 곱한 뒤 한다(`features_of_obs`). 그래서 float32 로 딱 떨어지지
않는 경계(예: c = 6 → 관측 0.3 → 6.0000002)에서는 float32 비교와 결과가 다를 수 있다. 언리얼 규칙 두뇌로 옮길 때는 같은 변환을 쓰거나
골든 표본을 경계에서 조금 벗어난 값으로 고른다(가능 조건 `rep_policy.feasible_mask` 는 float32 비교라 C++ 와 정확히 같다).
"""

from __future__ import annotations

import numpy as np

from env_v2.repertoire import BEHAVIOR_NAMES, FLEE, FREEZE, GRAZE, HIDE, SLEEP
from env_v2.world import daynight_seg_edges, obs_names

BEHAVIOR_IDS = {"graze": GRAZE, "flee": FLEE, "hide": HIDE, "freeze": FREEZE, "sleep": SLEEP,
                "stare": FREEZE, "look": FREEZE,         # v3 R2: X7·X8 은 FREEZE 다
                # v3 R2 보고만(사전 등록 5절 보조 교차·변형). 니치 모드만 뜻이 있다(`AUX_X`)
                "stare_still": FREEZE, "stare_far": FREEZE, "stare_chase": FREEZE, "look_hide": HIDE, "look_flee": FLEE}
# 보고만 하는 v3 R2 보조 규칙(사전 등록 5절). 판정에 쓰지 않고, mode 는 niche 만 받는다
AUX_X = ("stare_still", "stare_far", "stare_chase", "look_hide", "look_flee")
# 관측 alarm_heard 가 필요한 규칙
ALARM_X = ("look", "look_hide", "look_flee")
X_MODES = ("niche", "out", "cross")

# PREREG 3절 표 그대로(규칙 정의이고 세계 계수가 아니다). 거리·은신처 거리 단위는 세계 길이.
NICHES = {
    # FREEZE: 니치 = 위협이 보이고 거리 ≥ 8 & 접근 < 0.7, 밖 = 위협이 없을 때, 교차 = 위협이 6 안이거나 접근 ≥ 0.9
    "freeze": dict(far=8.0, slow=0.7, near=6.0, fast=0.9),
    # HIDE: 니치 = 위협이 보이고 은신처 ≤ 5, 밖 = 위협 없는 낮, 교차 = 위협이 보이고 은신처 > 10
    "hide": dict(cover_near=5.0, cover_far=10.0),
    # SLEEP: 니치 = 밤 & 에너지 ≥ 0.5 & 은신처 안, 밖 = 낮, 교차 = 밤 & 에너지 ≥ 0.5 & 은신처 밖
    "sleep": dict(energy=0.5),
    # GRAZE (FLEE 확인, 보고만): 바탕 규칙이 FLEE 를 고를 때 대신 계속 먹기(모든 모드가 같다)
    "graze": dict(),
    # v3 R2 X7 stare (FREEZE, results/v3/r2/PREREG.md 3절 G7): 니치 = 위협이 보이고 4 < 거리 ≤ 10 & 0.63 ≤ 접근 < 0.67(± 30° 안
    # 잠행 속력 정면 0.65) 또는 유지 줄(지금 FREEZE & 보이고 4 < 거리 ≤ 10 & hold_lo 0.45 ≤ 접근 < 0.67 — 멈춘 대치 0.5 포함,
    # 변경 기록 10-12 (2)), 밖 = 위협이 안 보일 때, 교차 = 위협이 보이고 거리 ≥ 8 & 접근 < 0.6 (먹기의 니치)
    "stare": dict(near=4.0, far=10.0, app_lo=0.63, app_hi=0.67, cross_far=8.0, cross_slow=0.6, hold_lo=0.45),
    # v3 R2 X8 look (FREEZE, G8): 니치 = 위협이 안 보이고 alarm_heard ≥ 0.4 & 은신처 거리 > 5, 밖 = 안 보이고 alarm_heard = 0 &
    # threat_recency < 0.2, 교차 = 안 보이고 0 < alarm_heard < 0.4 (약한·오래된 경보 — 먹기의 니치)
    "look": dict(alarm=0.4, cover_far=5.0, recency=0.2),
    # 보고만 (사전 등록 5절, 니치 모드만): G7 보조 교차 셋 — '노려보기 거리 안의 비접근'(보임 & 4 < 거리 ≤ 10 & 접근 < 0.55),
    # '너무 이른 노려보기'(보임 & 거리 > 10 & 0.6 ≤ 접근 < 0.7), '추격형 띠'(보임 & 4 < 거리 ≤ 10 & 0.75 ≤ 접근 < 0.9) → FREEZE.
    # G8 변형 둘 — '경보 → 숨기'(안 보임 & alarm_heard ≥ 0.4 & 은신처 ≤ 5 → HIDE), '경보 → 도망'(안 보임 & alarm_heard ≥ 0.4 → FLEE)
    "stare_still": dict(near=4.0, far=10.0, app_hi=0.55),
    "stare_far": dict(far=10.0, app_lo=0.6, app_hi=0.7),
    "stare_chase": dict(near=4.0, far=10.0, app_lo=0.75, app_hi=0.9),
    "look_hide": dict(alarm=0.4, cover_near=5.0),
    "look_flee": dict(alarm=0.4),
}
# 관측에서 찾는 칸 이름
_COLS = ("pred_count", "pred_dist", "energy", "cover_dist", "visibility", "pred_approach")
# 관측에 alarm_heard 가 있는 설정(v3 R2 기능 alarm)에서만 더 찾는 칸(look 규칙). 다른 설정의 규칙 스펙은 그대로 둔다
_ALARM_COLS = ("alarm_heard", "threat_recency")
# stare 니치의 유지 줄이 더 찾는 칸(지금 행동이 FREEZE 인가). stare 래퍼 스펙에만 넣는다(`_stare_geo`)
_STARE_COLS = ("beh_freeze",)


def with_obs_extra(cfg):
    """repertoire.obs_extra 만 켠 설정 사본(규칙이 접근 속력·현재 행동 관측을 읽게). 세계 동역학은 같다."""
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f["repertoire"] = dict(f["repertoire"], obs_extra=True)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _geom(cfg) -> dict:
    """규칙 래퍼 스펙에 넣는 관측 칸 번호와 단위(설정에서 채운다)."""
    names = list(obs_names(cfg))
    missing = [c for c in _COLS if c not in names]
    if missing:
        raise ValueError(f"손 규칙은 관측 {missing} 가 필요하다. repertoire.obs_extra 를 켠 설정을 쓴다(with_obs_extra)")
    dn = cfg.v2["features"]["daynight"]
    night, day = daynight_seg_edges(float(dn["detect_night"]))
    cols = {c: names.index(c) for c in _COLS}
    if _ALARM_COLS[0] in names:
        cols.update({c: names.index(c) for c in _ALARM_COLS})
    return dict(cols=cols, see_r=float(cfg.see_r),
                cover_norm=float(cfg.obs_cover_norm), night_edge=float(night), day_edge=float(day))


def _stare_geo(cfg, geo: dict) -> dict:
    """stare 래퍼의 관측 칸: `_geom` + beh_freeze(유지 줄). 다른 규칙의 스펙은 바꾸지 않으려고 stare 에만 더한다."""
    names = list(obs_names(cfg))
    missing = [c for c in _STARE_COLS if c not in names]
    if missing:
        raise ValueError(f"stare 규칙은 관측 {missing} 가 필요하다(repertoire.obs_extra 를 켠 설정, with_obs_extra)")
    return dict(geo, cols=dict(geo["cols"], **{c: names.index(c) for c in _STARE_COLS}))


def rule_spec(cfg, theta: float, approach: float, *, x: str | None = None, mode: str = "niche", slots=None) -> dict:
    """정책 스펙: 바탕 GRAZE 요청 → R_base(θ, a) → (선택) 행동 X 규칙. `slots` 는 X 를 쓰는 슬롯(None = 모두)."""
    geo = _geom(cfg)
    wraps = [dict(factory="repertoire_rules:base_rule", theta=float(theta), approach=float(approach), **geo)]
    if x is not None:
        if x not in NICHES or mode not in X_MODES:
            raise ValueError(f"x 는 {sorted(NICHES)}, mode 는 {X_MODES} 중 하나다. 받은 값: {x!r}, {mode!r}")
        wraps.append(x_wrap(cfg, x, mode, slots, geo))
    return {"policy": {"kind": "fixed", "action": [float(GRAZE)]}, "wrap": wraps}


def x_wrap(cfg, x: str, mode: str = "niche", slots=None, geo: dict | None = None) -> dict:
    """행동 X 규칙 래퍼 스펙 하나(`rule_spec` 의 둘째 래퍼). 여러 X 를 겹쳐 씌울 때(v3 R2 무리 확인) 쓴다 — 뒤에 씌운 규칙이 앞
    규칙을 덮는다. 보조 규칙(`AUX_X`)은 niche 모드만, alarm 규칙(`ALARM_X`)은 관측 alarm_heard 가 있는 설정에서만 받는다."""
    geo = _geom(cfg) if geo is None else geo
    if x not in NICHES or mode not in X_MODES:
        raise ValueError(f"x 는 {sorted(NICHES)}, mode 는 {X_MODES} 중 하나다. 받은 값: {x!r}, {mode!r}")
    if x in AUX_X and mode != "niche":
        raise ValueError(f"보조 규칙 {x} 는 niche 모드만 있다(사전 등록 5절 보고만). 받은 값: {mode!r}")
    if x in ALARM_X and _ALARM_COLS[0] not in geo["cols"]:
        raise ValueError(f"{x} 규칙은 관측 alarm_heard 가 필요하다(features.alarm 을 켠 설정, configs/v3_r2_w8_on.yaml)")
    if x == "stare":
        geo = _stare_geo(cfg, geo)
    return dict(factory="repertoire_rules:x_rule", x=x, mode=mode,
                slots=None if slots is None else [int(v) for v in slots], **NICHES[x], **geo)


def features_of_obs(o: np.ndarray, spec: dict) -> dict:
    """관측 → 규칙 입력: seen, dist(가장 가까운 보이는 위협, 안 보이면 inf), approach, cover_d, in_cover, energy, night, day.
    alarm_heard 칸이 있는 스펙(v3 R2 기능 alarm)은 alarm·recency 도 낸다."""
    c = spec["cols"]
    o = np.asarray(o, dtype=np.float64)
    seen = o[:, c["pred_count"]] > 0.0
    vis = o[:, c["visibility"]]
    out = dict(seen=seen, dist=np.where(seen, o[:, c["pred_dist"]] * spec["see_r"], np.inf),
               approach=o[:, c["pred_approach"]], cover_d=o[:, c["cover_dist"]] * spec["cover_norm"],
               in_cover=o[:, c["cover_dist"]] <= 0.0, energy=o[:, c["energy"]],
               night=vis < spec["night_edge"], day=vis >= spec["day_edge"])
    if _ALARM_COLS[0] in c:
        out["alarm"] = o[:, c["alarm_heard"]]
        out["recency"] = o[:, c["threat_recency"]]
    if _STARE_COLS[0] in c:             # stare 유지 줄: 지금 행동이 FREEZE (one-hot)
        out["freeze_now"] = o[:, c["beh_freeze"]] > 0.5
    if _R3_COLS[1] in c:                # v3 R3 규칙(`r3_geo`): K 의 기억 칸과 '도주 중' F
        out["recency"] = o[:, c["threat_recency"]]
        out["flee_now"] = o[:, c["beh_flee"]] > 0.5
    return out


class _Wrap:
    def observe_done(self, done):
        f = getattr(self.base, "observe_done", None)
        if f is not None:
            f(done)


class BaseRule(_Wrap):
    """R_base(θ, a). 바탕 정책의 요청은 쓰지 않는다(모든 개체를 덮는다). X 를 쓰지 않는다(GRAZE·FLEE 만)."""

    def __init__(self, base, spec):
        if spec.get("night_sleep") is not None:
            raise ValueError("R_base 는 밤 잠 선택지가 없다(거주 규칙은 X 를 쓰지 않는다, PREREG 2절)")
        self.base, self.spec = base, spec
        self.theta, self.approach = float(spec["theta"]), float(spec["approach"])

    def decide(self, obs) -> np.ndarray:
        f = features_of_obs(obs, self.spec)
        flee = f["seen"] & ((f["dist"] <= self.theta) | (f["approach"] >= self.approach))
        return np.where(flee, FLEE, GRAZE)

    def __call__(self, obs):
        self.base(obs)                       # 바탕 정책의 상태(있으면)를 같은 호출 순서로 진행시킨다
        return self.decide(obs).astype(np.float64)[:, None]


class XRule(_Wrap):
    """행동 X 규칙. 바탕 규칙의 요청 위에 `mode` 조건을 만족하는 (`slots` 의) 개체만 X 로 덮는다."""

    def __init__(self, base, spec):
        self.base, self.spec = base, spec
        self.x, self.mode = spec["x"], spec["mode"]
        self.slots = None if spec.get("slots") is None else np.asarray(spec["slots"], dtype=np.int64)

    def mask(self, obs, base_req: np.ndarray) -> np.ndarray:
        """X 를 쓸 개체 (N,) bool (슬롯 제한 포함)."""
        f, s = features_of_obs(obs, self.spec), self.spec
        seen, mode = f["seen"], self.mode
        if self.x == "freeze":
            if mode == "niche":
                m = seen & (f["dist"] >= s["far"]) & (f["approach"] < s["slow"])
            elif mode == "out":
                m = ~seen
            else:                               # 교차: 도망 대신 얼기
                m = seen & ((f["dist"] < s["near"]) | (f["approach"] >= s["fast"])) & (base_req == FLEE)
        elif self.x == "hide":
            if mode == "niche":
                m = seen & (f["cover_d"] <= s["cover_near"])
            elif mode == "out":
                m = ~seen & f["day"]
            else:                               # 교차: 도망 대신 숨기
                m = seen & (f["cover_d"] > s["cover_far"]) & (base_req == FLEE)
        elif self.x == "graze":
            m = base_req == FLEE
        elif self.x == "stare":                 # v3 R2 X7 (G7)
            if mode == "niche":
                rng = seen & (f["dist"] > s["near"]) & (f["dist"] <= s["far"])
                m = rng & (f["approach"] >= s["app_lo"]) & (f["approach"] < s["app_hi"])
                if "freeze_now" in f:           # 유지 줄: 이미 노려보는 중이면 멈춘 대치(접근 0.5)에서도 FREEZE
                    m = m | (rng & f["freeze_now"] & (f["approach"] >= s["hold_lo"]) & (f["approach"] < s["app_hi"]))
            elif mode == "out":
                m = ~seen
            else:                               # 교차: 멀고 다가오지 않는 위협(먹기의 니치)
                m = seen & (f["dist"] >= s["cross_far"]) & (f["approach"] < s["cross_slow"])
        elif self.x == "look":                  # v3 R2 X8 (G8)
            if "alarm" not in f:
                raise ValueError("look 규칙은 관측 alarm_heard 가 필요하다(features.alarm 을 켠 설정)")
            if mode == "niche":
                m = ~seen & (f["alarm"] >= s["alarm"]) & (f["cover_d"] > s["cover_far"])
            elif mode == "out":
                m = ~seen & (f["alarm"] == 0.0) & (f["recency"] < s["recency"])
            else:                               # 교차: 약한·오래된 경보
                m = ~seen & (f["alarm"] > 0.0) & (f["alarm"] < s["alarm"])
        elif self.x in AUX_X:                   # v3 R2 보고만(니치 모드만)
            if mode != "niche":
                raise ValueError(f"보조 규칙 {self.x} 는 niche 모드만 있다")
            if self.x.startswith("look") and "alarm" not in f:
                raise ValueError(f"{self.x} 규칙은 관측 alarm_heard 가 필요하다(features.alarm 을 켠 설정)")
            if self.x == "stare_still":
                m = seen & (f["dist"] > s["near"]) & (f["dist"] <= s["far"]) & (f["approach"] < s["app_hi"])
            elif self.x == "stare_far":
                m = seen & (f["dist"] > s["far"]) & (f["approach"] >= s["app_lo"]) & (f["approach"] < s["app_hi"])
            elif self.x == "stare_chase":
                m = (seen & (f["dist"] > s["near"]) & (f["dist"] <= s["far"]) & (f["approach"] >= s["app_lo"])
                     & (f["approach"] < s["app_hi"]))
            elif self.x == "look_hide":
                m = ~seen & (f["alarm"] >= s["alarm"]) & (f["cover_d"] <= s["cover_near"])
            else:                               # look_flee
                m = ~seen & (f["alarm"] >= s["alarm"])
        else:                                   # sleep
            fed = f["energy"] >= s["energy"]
            if mode == "niche":
                m = f["night"] & fed & f["in_cover"]
            elif mode == "out":
                m = f["day"]
            else:
                m = f["night"] & fed & ~f["in_cover"]
            m = m & (base_req != FLEE)
        if self.slots is not None:
            sl = np.zeros(len(m), dtype=bool)
            sl[self.slots[self.slots < len(m)]] = True
            m = m & sl
        return m

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64, copy=True)
        m = self.mask(obs, np.floor(a[:, 0]).astype(np.int64))
        a[m, 0] = float(BEHAVIOR_IDS[self.x])
        return a


def fsm_r2_spec(cfg, allowed=("graze", "flee", "hide", "freeze"), *, stare: bool = False, look: bool = True,
                theta: float = 4.0, approach: float = 0.9) -> dict:
    """FSM_R2 (언리얼 규칙 두뇌, 대조군 — 명세 RL_V3_R2_SPEC.md 4절): R1 FSM(`eval_v3.fsm_spec` 의 near 판: R_base(θ 4, a 0.9) +
    목록 행동의 니치 규칙)에 R2 세계에 넣은 장치의 줄을 더한다. 우선순위 HIDE(보임 & 은신처 ≤ 5) > FREEZE 가까운 판(보임 &
    (거리 < 6 또는 접근 ≥ 0.9), 바탕이 FLEE) > stare > look > SLEEP(목록에 있으면) > R_base. 뒤에 씌운 규칙이 앞 규칙을 덮으므로
    씌우는 순서는 우선순위의 반대다. stare·look 은 FREEZE 가 목록에 있을 때만 넣는다(`stare`·`look` 인자). look 은 관측
    alarm_heard 가 있는 설정에서만 쓸 수 있다.

    기본값은 R2 세계(v3_r1 + 경보 M8, 사람 결정 10-13 — 노려보기 M7 은 R2 에서 뺀다, 사전 등록 results/v3/r2/PREREG.md 변경 기록
    10-13 (8))의 FSM_R2 = R_base(4, 0.9) + look + R0 HIDE 니치 + R0 가까운 위협 얼기, 우선순위 HIDE > FREEZE 가까운 판 > look >
    R_base 다(stare 줄 없음). `stare=True` 는 두 장치를 함께 켰던 앞선 실행(10-12 의 합친 세계 확인 results/v3/r2/wr2_both, 그때의
    모방 초기화 교사·ws_baseline)의 FSM_R2(stare 줄 포함)를 재현할 때만 쓴다. 관문 도구 invasion_r2.py 는 두 인자를 늘 직접 준다."""
    geo = _geom(cfg)
    if look and "freeze" in allowed and _ALARM_COLS[0] not in geo["cols"]:
        raise ValueError("FSM_R2 의 look 줄은 관측 alarm_heard 가 필요하다(features.alarm 을 켠 설정). 경보가 없는 세계는 look=False")
    spec = rule_spec(cfg, theta, approach)
    order = [("sleep", "niche")] if "sleep" in allowed else []
    if "freeze" in allowed:
        order += ([("look", "niche")] if look else []) + ([("stare", "niche")] if stare else []) + [("freeze", "cross")]
    if "hide" in allowed:
        order.append(("hide", "niche"))
    for x, mode in order:
        g = _stare_geo(cfg, geo) if x == "stare" else geo
        spec["wrap"].append(dict(factory="repertoire_rules:x_rule", x=x, mode=mode, slots=None, **NICHES[x], **g))
    return spec


def base_rule(base, spec, seed):
    return BaseRule(base, spec)


def x_rule(base, spec, seed):
    return XRule(base, spec)


# --------------------------------------------------------------------- #
# v3 R3 관문 규칙 (사전 등록 results/v3/r3/PREREG.md 4·5·12절, 모듈 docstring 'v3 R3')
# --------------------------------------------------------------------- #

# 규칙 이름 → 관문 이름(사전 등록 16-1)
R3_GATE_NAME = {"keep": "G1", "keep_hide": "G1-H", "run": "G2", "leave": "G3", "crouch": "G4a", "shelter_all": "G0",
                "camp": "G0b", "early": "G6", "sleep_r3": "G5", "camp_sleep": "G0b-S"}
R3_X = tuple(R3_GATE_NAME)
# niche 모드만 있는 규칙: G1-H 보고 팔, 악용 점검(기준 (2)형만 본다)
R3_SINGLE = ("keep_hide", "shelter_all", "camp", "camp_sleep")
R3_EXPLOIT = ("shelter_all", "camp", "camp_sleep")
# 묶음 B(SLEEP, H8): SLEEP 을 허용 목록에 넣은 판 4 세계에서만
R3_SLEEP_X = ("sleep_r3", "camp_sleep")
# 규칙이 요청하는 행동. keep_hide(c < 15 면 HIDE, 아니면 FLEE)·camp_sleep(K 면 HIDE, 아니면 SLEEP)은 개체마다 다르고 여기 값은 주 행동이다
R3_X_BEHAVIOR = {"keep": FLEE, "keep_hide": HIDE, "run": HIDE, "leave": GRAZE, "crouch": HIDE, "shelter_all": HIDE,
                 "camp": HIDE, "early": FLEE, "sleep_r3": SLEEP, "camp_sleep": HIDE}
# 관측 계약 값(사전 등록 4절 '가능 조건'): K 의 기억 문턱(= rep_policy.THREAT_RECENCY_OBS), HIDE 가능 은신처 거리(= rep_policy.HIDE_COVER_OBS
# 0.75 × obs_cover_norm 20). torch 를 싣지 않으려고 여기 다시 적는다 — 시험이 rep_policy 값과 같은지 본다
R3_RECENCY = 0.2
R3_HIDE_C = 15.0
# 사전 등록 5-1 니치 표 그대로(규칙 정의이고 세계 계수가 아니다). 거리·은신처 거리 단위는 세계 길이. 열쇠: 니치(N)·니치 밖(o_)·교차(x_)
R3_NICHES = {
    # G1 계속 도망: N = F & s & a ≥ 0.6 & d < 10 & c > 0, O = ¬s & K & c > 0, C = F & s & a < 0.5 & d ≥ 8 & c > 0
    "keep": dict(app=0.6, d=10.0, x_app=0.5, x_d=8.0),
    # G1-H (보고만): G1 N 에서 c < 15 면 HIDE, 아니면 FLEE(G1 침입과 같게)
    "keep_hide": dict(app=0.6, d=10.0, hide_c=R3_HIDE_C),
    # G2 은신처로 달려가기: N = s & 0 < c ≤ 6 & d ≥ 6, O = ¬s & K & 0 < c < 15, C = s & 10 < c < 15 & 바탕 요청 FLEE
    "run": dict(c=6.0, d=6.0, o_c=R3_HIDE_C, x_lo=10.0, x_hi=R3_HIDE_C),
    # G3 배고프면 나가기 (X = GRAZE): N = c = 0 & K & (¬s ∨ d ≥ 10) & E < 0.35, O = c = 0 & s & d < 6, C = c = 0 & K & ¬s & E > 0.7
    "leave": dict(d=10.0, e=0.35, o_d=6.0, x_e=0.7),
    # G4a 은신처 안 웅크림: N = c = 0 & s & d < 6, O = c = 0 & ¬s & K & E ≤ 0.7, C = c = 0 & s & d ≥ 8 & a < 0.7
    "crouch": dict(d=6.0, o_e=0.7, x_d=8.0, x_app=0.7),
    # G0 늘 은신처: K & c < 15 (가능하면 늘)
    "shelter_all": dict(c=R3_HIDE_C),
    # G0b 덤불 눌러앉기: c = 0 & K
    "camp": dict(),
    # G6 미리 떠나기 (θ·a* 는 거주 R_base 문턱): N = ¬F & s & θ < d < 8 & 0.6 ≤ a < a* & c > 0,
    # O = ¬F & s & d ≥ 12 & a < 0.55 & c > 0, C = ¬F & s & θ < d < 8 & a < 0.55 & c > 0.
    # 교차의 거리 위 끝은 x_d_hi 로 따로 둔다. 보정 1 은 니치(d_hi)만 좁히고 교차는 그대로다(9-1 '보정은 니치를 좁히는 것뿐')
    "early": dict(d_hi=8.0, app=0.6, o_d=12.0, x_app=0.55, x_d_hi=8.0),
    # G5 밤에 은신처에서 자기: N = 밤 & c = 0 & ¬K & E ≥ 0.5, O = 낮 & ¬K, C = 밤 & c > 0 & ¬K & E ≥ 0.5
    "sleep_r3": dict(e=0.5),
    # G0b-S 덤불에서 안 나감: c = 0 → K 면 HIDE, ¬K 면 SLEEP
    "camp_sleep": dict(),
}
# 보정 1 (사전 등록 9-1·5-1 표 '실패 때 보정' 1)): 니치만 좁힌다. G1-H 는 G1 의 니치를 따른다. 보정 2 는 규칙이 아니다(G2 의 H15 는 사람 승인)
R3_CAL1 = {"keep": dict(app=0.75, d=8.0), "keep_hide": dict(app=0.75, d=8.0), "run": dict(c=4.0), "leave": dict(e=0.2),
           "early": dict(d_hi=7.0, app=0.62)}
# 판정 U (사전 등록 15-3): U_ESC 와 관문 니치의 U. hide = U_HIDE′(G4a 니치·교차, R1b 정의와 같다)
R3_U = ("esc", "keep", "run", "leave", "hide", "early")
R3_U_GATE = {"keep": "keep", "run": "run", "leave": "leave", "hide": "crouch", "early": "early"}
R3_ESC = dict(app=0.75, d=10.0)
# FSM_R3 의 관문 줄(12-1 의 줄 1·2·3·5·6). 줄 4(R_base 핵심 줄)와 줄 7(GRAZE)은 늘 있다. 잠 줄은 묶음 B 가 통과했을 때만(sleep)
FSM_R3_LINES = ("crouch", "leave", "run", "keep", "early")
# R3 래퍼가 더 읽는 관측 칸(`r3_geo`)
_R3_COLS = ("threat_recency", "beh_flee")


def r3_params(x: str, cal: int = 0) -> dict:
    """규칙 x 의 니치 문턱(보정 1 이면 좁힌 값)."""
    if x not in R3_NICHES:
        raise ValueError(f"R3 규칙은 {list(R3_X)} 중 하나다. 받은 값: {x!r}")
    if cal not in (0, 1):
        raise ValueError(f"보정 회차는 0(원래 니치) 또는 1 이다(사전 등록 9-1). 받은 값: {cal!r}")
    if cal and x not in R3_CAL1:
        raise ValueError(f"{x} 는 보정 1 이 없다(사전 등록 5-1 표). 보정이 있는 규칙: {sorted(R3_CAL1)}")
    p = dict(R3_NICHES[x])
    if cal:
        p.update(R3_CAL1[x])
    return p


def r3_allowed(cfg, sleep: bool = False) -> tuple[str, ...]:
    """설정의 허용 목록(train.repertoire.allowed, 계약 순서). `sleep` 이면 SLEEP 을 더한다(묶음 B 판 4 세계, 메모리 사본)."""
    rp = ((cfg.v2.get("train") or {}).get("repertoire") or {})
    names = list(rp.get("allowed") or [])
    if not names:
        raise ValueError("R3 규칙은 train.repertoire.allowed 가 있는 설정에서만 쓴다(configs/v3_r3_on.yaml)")
    if sleep and "sleep" not in names:
        names.append("sleep")
    return tuple(b for b in BEHAVIOR_NAMES if b in names)


def r3_geo(cfg, geo: dict | None = None) -> dict:
    """R3 래퍼 스펙의 관측 칸: `_geom` + threat_recency·beh_flee. 다른 규칙의 스펙은 바꾸지 않으려고 R3 래퍼에만 더한다."""
    geo = _geom(cfg) if geo is None else geo
    names = list(obs_names(cfg))
    missing = [c for c in _R3_COLS if c not in names]
    if missing:
        raise ValueError(f"R3 규칙은 관측 {missing} 가 필요하다(repertoire.obs_extra 를 켠 설정)")
    return dict(geo, cols=dict(geo["cols"], **{c: names.index(c) for c in _R3_COLS}))


def r3_known(f: dict) -> np.ndarray:
    """K = s ∨ threat_recency ≥ 0.2 (사전 등록 5-1, 마스크 판 2 의 '위협을 안다'와 같다)."""
    return f["seen"] | (f["recency"] >= R3_RECENCY)


def r3_cond(x: str, mode: str, f: dict, p: dict, theta: float | None = None, approach: float | None = None,
            base_req: np.ndarray | None = None) -> np.ndarray:
    """규칙 x 의 `mode`(niche·out·cross) 조건 (N,) bool — 사전 등록 5-1 표(`R3_NICHES` 주석) 그대로. `f` 는 R3 스펙의
    `features_of_obs`(recency·flee_now 포함), `p` 는 `r3_params`. early 는 거주 θ·a* 가, run 의 교차는 바탕 요청(base_req)이 필요하다."""
    s, d, a = f["seen"], f["dist"], f["approach"]
    c, inc, E = f["cover_d"], f["in_cover"], f["energy"]
    K, F = r3_known(f), f["flee_now"]
    out_c = ~inc                                      # c > 0
    if mode not in X_MODES:
        raise ValueError(f"mode 는 {X_MODES} 중 하나다. 받은 값: {mode!r}")
    if x in R3_SINGLE and mode != "niche":
        raise ValueError(f"{x} 는 niche 모드만 있다(보고 팔·악용 점검)")
    if x in ("keep", "keep_hide"):
        if mode == "niche":
            return F & s & (a >= p["app"]) & (d < p["d"]) & out_c
        if mode == "out":
            return ~s & K & out_c
        return F & s & (a < p["x_app"]) & (d >= p["x_d"]) & out_c
    if x == "run":
        if mode == "niche":
            return s & out_c & (c <= p["c"]) & (d >= p["d"])
        if mode == "out":
            return ~s & K & out_c & (c < p["o_c"])
        if base_req is None:
            raise ValueError("run 의 교차는 바탕 요청이 FLEE 인 개체에만 건다(base_req 가 필요하다)")
        return s & (c > p["x_lo"]) & (c < p["x_hi"]) & (np.asarray(base_req) == FLEE)
    if x == "leave":
        if mode == "niche":
            return inc & K & (~s | (d >= p["d"])) & (E < p["e"])
        if mode == "out":
            return inc & s & (d < p["o_d"])
        return inc & K & ~s & (E > p["x_e"])
    if x == "crouch":
        if mode == "niche":
            return inc & s & (d < p["d"])
        if mode == "out":
            return inc & ~s & K & (E <= p["o_e"])
        return inc & s & (d >= p["x_d"]) & (a < p["x_app"])
    if x == "shelter_all":
        return K & (c < p["c"])
    if x == "camp":
        return inc & K
    if x == "early":
        if theta is None or approach is None:
            raise ValueError("early(G6) 의 니치는 거주 R_base 의 θ·a* 가 필요하다")
        if mode == "niche":
            return ~F & s & (d > theta) & (d < p["d_hi"]) & (a >= p["app"]) & (a < approach) & out_c
        if mode == "out":
            return ~F & s & (d >= p["o_d"]) & (a < p["x_app"]) & out_c
        return ~F & s & (d > theta) & (d < p["x_d_hi"]) & (a < p["x_app"]) & out_c
    if x == "sleep_r3":
        if mode == "niche":
            return f["night"] & inc & ~K & (E >= p["e"])
        if mode == "out":
            return f["day"] & ~K
        return f["night"] & out_c & ~K & (E >= p["e"])
    if x == "camp_sleep":
        return inc.copy()
    raise ValueError(f"R3 규칙은 {list(R3_X)} 중 하나다. 받은 값: {x!r}")


def r3_action(x: str, f: dict, p: dict) -> np.ndarray:
    """규칙 x 가 요청하는 행동 (N,) int64. keep_hide·camp_sleep 만 개체마다 다르다."""
    n = len(f["seen"])
    if x == "keep_hide":
        return np.where(f["cover_d"] < p["hide_c"], HIDE, FLEE).astype(np.int64)
    if x == "camp_sleep":
        return np.where(r3_known(f), HIDE, SLEEP).astype(np.int64)
    return np.full(n, R3_X_BEHAVIOR[x], dtype=np.int64)


def r3_feasible(obs, spec: dict, f: dict | None = None) -> np.ndarray:
    """허용 ∧ 가능 (N, 5) bool (사전 등록 4절 '고를 수 있는 자리'). 가능 칸은 학습 마스크와 같은 함수(`rep_policy.feasible_mask`, 판 2)
    이고, 묶음 B 판 4(`sleep_v4`)는 SLEEP 가능 = ¬K 를 더한다. 결정 시점 칸(rep_peek)은 보지 않는다 — 세계가 결정 시점에만 요청을
    읽으므로 결정 밖 스텝의 요청은 쓰이지 않는다."""
    from env_v2.rep_policy import feasible_mask           # torch 를 싣는다(규칙을 쓸 때만)

    o = np.asarray(obs)
    fm = feasible_mask(o, spec["obs_names"]) & np.array([b in spec["allowed"] for b in BEHAVIOR_NAMES])[None, :]
    if spec.get("sleep_v4"):
        f = features_of_obs(o, spec) if f is None else f
        fm[:, SLEEP] &= ~r3_known(f)
    return fm


def r3_wrap(cfg, x: str, mode: str = "niche", slots=None, *, theta: float | None = None, approach: float | None = None,
            cal: int = 0, sleep: bool = False, feasible: bool = True, geo: dict | None = None) -> dict:
    """R3 규칙 래퍼 스펙 하나(바탕 규칙 위에 씌운다, 뒤에 씌운 규칙이 앞 규칙을 덮는다). `slots` 는 X 를 쓰는 슬롯(None = 모두),
    `cal` 은 보정 회차(0·1), `sleep` 은 묶음 B(허용 목록에 SLEEP, 판 4 — SLEEP 가능 = ¬K), `feasible` 은 가능 조건 거르기(사전 등록 4절,
    기본 켬 — 끄는 것은 시험의 대조뿐이다). early 는 거주 θ·a* 를, 묶음 B 규칙은 `sleep` 을 꼭 받는다."""
    if x not in R3_NICHES or mode not in X_MODES:
        raise ValueError(f"x 는 {list(R3_X)}, mode 는 {X_MODES} 중 하나다. 받은 값: {x!r}, {mode!r}")
    if x in R3_SINGLE and mode != "niche":
        raise ValueError(f"{x} 는 niche 모드만 있다(보고 팔·악용 점검, 사전 등록 5-1)")
    if x == "early" and (theta is None or approach is None):
        raise ValueError("early(G6) 의 니치는 거주 R_base 의 θ·a* 가 필요하다(theta, approach)")
    if x in R3_SLEEP_X and not sleep:
        raise ValueError(f"{x} 는 묶음 B(SLEEP 을 연 판 4 세계)에서만 쓴다(sleep=True)")
    return dict(factory="repertoire_rules:r3_rule", x=x, mode=mode, slots=None if slots is None else [int(v) for v in slots],
                cal=int(cal), niche=r3_params(x, cal), theta=None if theta is None else float(theta),
                approach=None if approach is None else float(approach), allowed=list(r3_allowed(cfg, sleep)),
                sleep_v4=bool(sleep), feasible=bool(feasible), obs_names=list(obs_names(cfg)), **r3_geo(cfg, geo))


def r3_rule_spec(cfg, theta: float, approach: float, *, resident: str = "rbase", x: str | None = None, mode: str = "niche",
                 slots=None, cal: int = 0, sleep: bool = False) -> dict:
    """R3 정책 스펙: 바탕 GRAZE 요청 → R_base(θ, a) → (resident = camp 면, G3 의 거주 규칙) 'c = 0 & K → HIDE' → (선택) R3 규칙 X."""
    if resident not in ("rbase", "camp"):
        raise ValueError(f"거주 규칙은 rbase(R_base) 또는 camp(G3 거주 = R_base + camp)다. 받은 값: {resident!r}")
    spec = rule_spec(cfg, theta, approach)
    if resident == "camp":
        spec["wrap"].append(r3_wrap(cfg, "camp", "niche", None, sleep=sleep))
    if x is not None:
        spec["wrap"].append(r3_wrap(cfg, x, mode, slots, theta=theta, approach=approach, cal=cal, sleep=sleep))
    return spec


class R3Rule(_Wrap):
    """R3 규칙 X. 바탕 규칙의 요청 위에 `mode` 조건을 만족하고 (`slots` 의) 고를 수 있는(허용 ∧ 가능) 개체만 X 로 덮는다."""

    def __init__(self, base, spec):
        self.base, self.spec = base, spec
        self.x, self.mode, self.p = spec["x"], spec["mode"], spec["niche"]
        self.theta, self.approach = spec.get("theta"), spec.get("approach")
        self.slots = None if spec.get("slots") is None else np.asarray(spec["slots"], dtype=np.int64)

    def target(self, obs, base_req: np.ndarray, slots: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """(덮을 개체 (N,) bool, 요청 행동 (N,) int64). `slots` 가 거짓이면 슬롯 제한을 빼고 낸다(사건 조건 지표)."""
        o = np.asarray(obs)
        f = features_of_obs(o, self.spec)
        m = r3_cond(self.x, self.mode, f, self.p, self.theta, self.approach, base_req)
        act = r3_action(self.x, f, self.p)
        if self.spec["feasible"]:
            m = m & r3_feasible(o, self.spec, f)[np.arange(len(m)), act]
        if slots and self.slots is not None:
            sl = np.zeros(len(m), dtype=bool)
            sl[self.slots[self.slots < len(m)]] = True
            m = m & sl
        return m, act

    def __call__(self, obs):
        a = np.array(self.base(obs), dtype=np.float64, copy=True)
        m, act = self.target(obs, np.floor(a[:, 0]).astype(np.int64))
        a[m, 0] = act[m].astype(np.float64)
        return a


def fsm_r3_spec(cfg, theta: float, approach: float, *, lines=FSM_R3_LINES, cal=(), sleep: bool = False) -> dict:
    """FSM_R3 (교사·언리얼 규칙 두뇌, 사전 등록 12-1): 관측만 읽고 위에서부터 처음 맞는 줄을 쓴다.
      1. (crouch) c = 0 & s & d < 6 → HIDE                       — G4a 니치
      2. (leave)  c = 0 & K & ¬s & E > 0.7 → HIDE                — G3 교차(배부르면 숨어 있기)
      3. (run)    c > 0 & s & c ≤ 6 & d ≥ 6 → HIDE               — G2 니치(보정 1 이면 c ≤ 4)
      4.          c > 0 & s & (d ≤ θ ∨ a ≥ a*) → FLEE            — 거주 R_base 의 핵심 줄(은신처 안에서는 도망하지 않는다)
      5. (keep)   F & s & a ≥ 0.6 & d < 10 & c > 0 → FLEE         — G1 니치(보정 1 이면 a ≥ 0.75 & d < 8)
      6. (early)  ¬F & s & θ < d < 8 & 0.6 ≤ a < a* & c > 0 → FLEE — G6 니치(보정 1 이면 d < 7 & a ≥ 0.62)
      (sleep)     밤 & c = 0 & ¬K & E ≥ 0.5 → SLEEP              — 묶음 B 가 통과해 SLEEP 을 열 때만
      7.          그 밖 → GRAZE
    `lines` 는 넣을 관문 줄(통과·조건부 통과한 관문, 9-2 표), `cal` 은 보정 1 을 쓴 관문. 얼기 줄과 땅 줄은 없다. 요청이 허용 ∧ 가능
    밖이면 GRAZE 로 바꾼다(eval_v3.ConstRequest 와 같다)."""
    lines = tuple(lines)
    bad = [x for x in lines if x not in FSM_R3_LINES]
    if bad:
        raise ValueError(f"FSM_R3 의 관문 줄은 {list(FSM_R3_LINES)} 중에서 고른다. 받은 값: {bad}")
    cal = tuple(cal)
    bad = [x for x in cal if x not in R3_CAL1 or x not in lines]
    if bad:
        raise ValueError(f"보정 1 은 넣은 줄 가운데 보정이 있는 관문({sorted(R3_CAL1)})에만 건다. 받은 값: {bad}")
    niches = {x: r3_params(x, 1 if x in cal else 0) for x in FSM_R3_LINES}
    niches["sleep_r3"] = r3_params("sleep_r3")
    w = dict(factory="repertoire_rules:fsm_r3_rule", theta=float(theta), approach=float(approach),
             lines=[x for x in FSM_R3_LINES if x in lines], cal=[x for x in FSM_R3_LINES if x in cal], sleep=bool(sleep),
             niches=niches, allowed=list(r3_allowed(cfg, sleep)), sleep_v4=bool(sleep), feasible=True,
             obs_names=list(obs_names(cfg)), **r3_geo(cfg))
    return {"policy": {"kind": "fixed", "action": [float(GRAZE)]}, "wrap": [w]}


class FsmR3(_Wrap):
    """FSM_R3 (`fsm_r3_spec`). 바탕 정책의 요청은 쓰지 않는다(모든 개체를 덮는다). 상태가 없다."""

    def __init__(self, base, spec):
        self.base, self.spec = base, spec
        self.lines = tuple(spec["lines"])
        self.theta, self.approach = float(spec["theta"]), float(spec["approach"])

    def decide(self, obs) -> np.ndarray:
        o = np.asarray(obs)
        f = features_of_obs(o, self.spec)
        P, th, ast = self.spec["niches"], self.theta, self.approach
        conds, acts = [], []
        if "crouch" in self.lines:
            conds.append(r3_cond("crouch", "niche", f, P["crouch"]))
            acts.append(HIDE)
        if "leave" in self.lines:
            conds.append(r3_cond("leave", "cross", f, P["leave"]))
            acts.append(HIDE)
        if "run" in self.lines:
            conds.append(r3_cond("run", "niche", f, P["run"]))
            acts.append(HIDE)
        conds.append(~f["in_cover"] & f["seen"] & ((f["dist"] <= th) | (f["approach"] >= ast)))
        acts.append(FLEE)
        if "keep" in self.lines:
            conds.append(r3_cond("keep", "niche", f, P["keep"]))
            acts.append(FLEE)
        if "early" in self.lines:
            conds.append(r3_cond("early", "niche", f, P["early"], th, ast))
            acts.append(FLEE)
        if self.spec["sleep"]:
            conds.append(r3_cond("sleep_r3", "niche", f, P["sleep_r3"]))
            acts.append(SLEEP)
        req = np.select(conds, acts, default=GRAZE).astype(np.int64)
        ok = r3_feasible(o, self.spec, f)[np.arange(len(req)), req]
        return np.where(ok, req, GRAZE).astype(np.int64)

    def __call__(self, obs):
        self.base(obs)
        return self.decide(obs).astype(np.float64)[:, None]


def r3_u_terms(f: dict, theta: float, approach: float, cal=()) -> dict:
    """판정 U 의 (첫 항 조건, 둘째 항 조건) (사전 등록 15-3 'U 정의', 보정 1 을 쓴 니치는 보정 뒤 정의). `f` 는 R3 스펙(`r3_geo`)의
    `features_of_obs`. U_RUN 교차의 '바탕 요청 FLEE' 는 같은 관측의 거주 R_base(θ, a*) 요청이다(상태 없는 규칙).
      U_ESC   = P(FLEE ∪ HIDE | s & a ≥ 0.75 & d < 10) − P(같은 것 | ¬s)
      U_KEEP  = P(FLEE ∪ 은신처 밖 HIDE | G1 N) − P(같은 것 | G1 C & ¬G2 N)
      U_RUN   = P(HIDE | G2 N) − P(HIDE | G2 C)
      U_LEAVE = P(GRAZE | G3 N) − P(GRAZE | G3 C)
      U_HIDE′ = P(HIDE | G4a N) − P(HIDE | G4a C)   (R1b 정의 그대로)
      U_EARLY = P(FLEE ∪ 은신처 밖 HIDE | G6 N) − P(같은 것 | G6 C & ¬G2 N)"""
    cal = set(cal)
    P = {x: r3_params(x, 1 if x in cal else 0) for x in ("keep", "run", "leave", "crouch", "early")}
    base = np.where(f["seen"] & ((f["dist"] <= theta) | (f["approach"] >= approach)), FLEE, GRAZE)
    g2n = r3_cond("run", "niche", f, P["run"])
    return {"esc": (f["seen"] & (f["approach"] >= R3_ESC["app"]) & (f["dist"] < R3_ESC["d"]), ~f["seen"]),
            "keep": (r3_cond("keep", "niche", f, P["keep"]), r3_cond("keep", "cross", f, P["keep"]) & ~g2n),
            "run": (g2n, r3_cond("run", "cross", f, P["run"], base_req=base)),
            "leave": (r3_cond("leave", "niche", f, P["leave"]), r3_cond("leave", "cross", f, P["leave"])),
            "hide": (r3_cond("crouch", "niche", f, P["crouch"]), r3_cond("crouch", "cross", f, P["crouch"])),
            "early": (r3_cond("early", "niche", f, P["early"], theta, approach),
                      r3_cond("early", "cross", f, P["early"], theta, approach) & ~g2n)}


def r3_u_hit(u: str, chosen: np.ndarray, f: dict) -> np.ndarray:
    """U 의 '고른 행동' 적중 (n,) bool. U_ESC = FLEE ∪ HIDE, U_KEEP·U_EARLY = FLEE ∪ 은신처 밖 HIDE(포기율 A 와 같은 묶음),
    U_RUN·U_HIDE′ = HIDE, U_LEAVE = GRAZE."""
    chosen = np.asarray(chosen)
    if u == "esc":
        return np.isin(chosen, (FLEE, HIDE))
    if u in ("keep", "early"):
        return (chosen == FLEE) | ((chosen == HIDE) & ~f["in_cover"])
    if u in ("run", "hide"):
        return chosen == HIDE
    if u == "leave":
        return chosen == GRAZE
    raise ValueError(f"R3 U 는 {list(R3_U)} 중 하나다. 받은 값: {u!r}")


def r3_u_prob(u: str, pi: np.ndarray, f: dict) -> np.ndarray:
    """`r3_u_hit` 의 확률 판 (n,) — 결정 시점 π(n, 5)에서 같은 묶음의 확률 합(학습 기록·조기 중단의 니치 π)."""
    pi = np.asarray(pi, dtype=np.float64)
    if u == "esc":
        return pi[:, FLEE] + pi[:, HIDE]
    if u in ("keep", "early"):
        return pi[:, FLEE] + pi[:, HIDE] * (~f["in_cover"])
    if u in ("run", "hide"):
        return pi[:, HIDE]
    if u == "leave":
        return pi[:, GRAZE]
    raise ValueError(f"R3 U 는 {list(R3_U)} 중 하나다. 받은 값: {u!r}")


def r3_rule(base, spec, seed):
    return R3Rule(base, spec)


def fsm_r3_rule(base, spec, seed):
    return FsmR3(base, spec)
