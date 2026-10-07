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
"""

from __future__ import annotations

import numpy as np

from env_v2.repertoire import FLEE, FREEZE, GRAZE, HIDE, SLEEP
from env_v2.world import daynight_seg_edges, obs_names

BEHAVIOR_IDS = {"graze": GRAZE, "flee": FLEE, "hide": HIDE, "freeze": FREEZE, "sleep": SLEEP}
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
}
# 관측에서 찾는 칸 이름
_COLS = ("pred_count", "pred_dist", "energy", "cover_dist", "visibility", "pred_approach")


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
    return dict(cols={c: names.index(c) for c in _COLS}, see_r=float(cfg.see_r),
                cover_norm=float(cfg.obs_cover_norm), night_edge=float(night), day_edge=float(day))


def rule_spec(cfg, theta: float, approach: float, *, x: str | None = None, mode: str = "niche", slots=None) -> dict:
    """정책 스펙: 바탕 GRAZE 요청 → R_base(θ, a) → (선택) 행동 X 규칙. `slots` 는 X 를 쓰는 슬롯(None = 모두)."""
    geo = _geom(cfg)
    wraps = [dict(factory="repertoire_rules:base_rule", theta=float(theta), approach=float(approach), **geo)]
    if x is not None:
        if x not in NICHES or mode not in X_MODES:
            raise ValueError(f"x 는 {sorted(NICHES)}, mode 는 {X_MODES} 중 하나다. 받은 값: {x!r}, {mode!r}")
        wraps.append(dict(factory="repertoire_rules:x_rule", x=x, mode=mode,
                          slots=None if slots is None else [int(s) for s in slots], **NICHES[x], **geo))
    return {"policy": {"kind": "fixed", "action": [float(GRAZE)]}, "wrap": wraps}


def features_of_obs(o: np.ndarray, spec: dict) -> dict:
    """관측 → 규칙 입력: seen, dist(가장 가까운 보이는 위협, 안 보이면 inf), approach, cover_d, in_cover, energy, night, day."""
    c = spec["cols"]
    o = np.asarray(o, dtype=np.float64)
    seen = o[:, c["pred_count"]] > 0.0
    vis = o[:, c["visibility"]]
    return dict(seen=seen, dist=np.where(seen, o[:, c["pred_dist"]] * spec["see_r"], np.inf),
                approach=o[:, c["pred_approach"]], cover_d=o[:, c["cover_dist"]] * spec["cover_norm"],
                in_cover=o[:, c["cover_dist"]] <= 0.0, energy=o[:, c["energy"]],
                night=vis < spec["night_edge"], day=vis >= spec["day_edge"])


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


def base_rule(base, spec, seed):
    return BaseRule(base, spec)


def x_rule(base, spec, seed):
    return XRule(base, spec)
