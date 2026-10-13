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
"""

from __future__ import annotations

import numpy as np

from env_v2.repertoire import FLEE, FREEZE, GRAZE, HIDE, SLEEP
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
