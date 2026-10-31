"""v2.4 낮밤 판정 도구 — 정책 스펙과 래퍼 (계획서 4.9.2, 6.3 대조군, 2-4·2-5 행).

`env_v2/rollout.py` 의 "모듈:함수" 래퍼 문법으로 쓴다(`{"factory": "daynight_v2:night_rest", ...}`). 관측 칸은 번호가
아니라 이름으로 찾는다(v2.1 위의 v2.4 는 visibility idx 7, to_transition idx 8. 계획서 4.2 의 9·10 은 앞 버전을 모두
했을 때 번호다).

- `c4_phase(spec, cfg)`: C4-phase — 관측 visibility·to_transition 을 낮 값 1·1 로 고정(계획서 6.3, 낮 고정 세계가 있어
  학습 분포 안이다). 입력 의존(위상 관측을 실제로 보는가)을 가린다.
- `night_energy_fix(base, spec, seed)`: 밤 구간(관측 visibility 로 나눈 구간)에서만 관측 4(energy)를 고정값으로 둔다 —
  C4-energy 밤 구간판(N5′ 의 입력 의존, 계획서 2단계 완료 기준).
- `night_rest(base, spec, seed)`: Utility v2 밤 규칙(계획서 2-4 행, 4.7 'Utility v2 … 밤이면 은신처로')을 바탕 정책 위에
  덧씌운다. 밤이고 포식자가 안 보이면: 은신처 밖이면 걷기로 은신처 쪽(cover 1, forage 0), 은신처 안이면 정지.
  fed_only 면 배부른(energy ≥ 0.5) 개체에만 건다('배고프면 밤에도 먹기' 변형). 침입 시험과 덧씌우기 기준선에 쓴다.
- `phase_seg_bins(cfg)`: C2-seg 위상판의 관측 구간(visibility 문턱 `daynight_seg_edges`, energy 0.5).
- `is_food_scarce(cfg, seed)`: 먹이 부족 세계(공급 상한 Σ r·cap0 < 기초 수요 N·energy_drain/food_energy_per_unit,
  보정 시드 20001 꼴. R10 의 '먹이가 모자란 세계'와 같은 식)인가와 두 값.
"""

from __future__ import annotations

import numpy as np

from env_v2.world import HUNGRY, World, daynight_seg_edges, obs_names

OBS_PRED_COUNT, OBS_ENERGY, OBS_COVER = 1, 4, 6


def _col(cfg_or_names, name: str) -> int:
    names = cfg_or_names if isinstance(cfg_or_names, (list, tuple)) else obs_names(cfg_or_names)
    return list(names).index(name)


def detect_night(cfg) -> float:
    return float(cfg.v2["features"]["daynight"]["detect_night"])


def c4_phase(spec: dict, cfg) -> dict:
    """C4-phase 스펙: 관측 visibility·to_transition 을 1·1 로 고정한다."""
    return add_wrap(spec, {"kind": "obs_fix", "dims": [_col(cfg, "visibility"), _col(cfg, "to_transition")],
                           "values": [1.0, 1.0]})


def phase_seg_bins(cfg, with_energy: bool = True) -> list[str]:
    """C2-seg 위상판 `--seg-bins` 토큰. 밤 | 박명 | 낮 (× energy 0.5)."""
    lo, hi = daynight_seg_edges(detect_night(cfg))
    toks = [f"visibility:{lo!r},{hi!r}"]
    if with_energy:
        toks.append("energy:0.5")
    return toks


class _Wrap:
    def observe_done(self, done):
        f = getattr(self.base, "observe_done", None)
        if f is not None:
            f(done)


class NightEnergyFix(_Wrap):
    """밤 구간 개체의 관측 4(energy)만 `value` 로 바꿔 바탕 정책에 넣는다."""

    def __init__(self, base, spec):
        self.base = base
        self.vis, self.night = int(spec["vis_col"]), float(spec["night_edge"])
        self.value = float(spec["value"])

    def __call__(self, obs):
        o = np.array(obs, dtype=np.float32, copy=True)
        night = o[:, self.vis] < self.night
        o[night, OBS_ENERGY] = self.value
        return self.base(o)


class NightRest(_Wrap):
    """Utility v2 밤 규칙 덧씌우기. 밤 = 관측 visibility < night_edge, 안 보임 = 관측 1 = 0.

    speed 열(4)은 걷기 값 0.5(문턱 1/3·2/3 사이) 또는 정지 값 0.0 으로, 조향은 forage 0·cover 1 로 덮는다(나머지 열은
    바탕 정책 그대로). 은신처 안(관측 6 = 0)이면 정지한다 — 정지는 움직이지 않으므로 cover 가중치만으로는 은신처에 갈 수
    없어 은신처 밖에서는 걷는다.
    """

    def __init__(self, base, spec):
        self.base = base
        self.vis, self.night = int(spec["vis_col"]), float(spec["night_edge"])
        self.fed_only = bool(spec.get("fed_only", False))
        self.slots = None if spec.get("slots") is None else np.asarray(spec["slots"], dtype=np.int64)

    def __call__(self, obs):
        o = np.asarray(obs)
        a = np.array(self.base(obs), dtype=np.float64, copy=True)
        rule = (o[:, self.vis] < self.night) & (o[:, OBS_PRED_COUNT] <= 0.0)
        if self.fed_only:
            rule &= o[:, OBS_ENERGY] >= HUNGRY
        if self.slots is not None:
            m = np.zeros(len(o), dtype=bool)
            m[self.slots[self.slots < len(o)]] = True
            rule &= m
        inside = o[:, OBS_COVER] <= 0.0
        a[rule, 0] = 0.0
        a[rule, 3] = 1.0
        a[rule, 4] = np.where(inside[rule], 0.0, 0.5)
        return a


def night_energy_fix(base, spec, seed):
    return NightEnergyFix(base, spec)


def night_rest(base, spec, seed):
    return NightRest(base, spec)


def rule_wrap(cfg, *, fed_only=False, slots=None, factory="night_rest", **extra) -> dict:
    """night_rest·night_energy_fix 래퍼 스펙(관측 칸·문턱을 설정에서 채운다)."""
    lo, _ = daynight_seg_edges(detect_night(cfg))
    w = {"factory": f"daynight_v2:{factory}", "vis_col": _col(cfg, "visibility"), "night_edge": lo}
    if factory == "night_rest":
        w.update(fed_only=bool(fed_only), slots=None if slots is None else [int(s) for s in slots])
    w.update(extra)
    return w


def add_wrap(spec: dict, *wraps: dict) -> dict:
    """스펙 위에 래퍼를 더한다. 이미 래퍼 스펙이면 목록 뒤에 붙인다(rollout.build_policy 는 한 단계만 푼다)."""
    if "wrap" in spec:
        return {"policy": spec["policy"], "wrap": list(spec["wrap"]) + list(wraps)}
    return {"policy": spec, "wrap": list(wraps)}


def take7(spec: dict) -> dict:
    """관측 7 모델(v2.1)을 관측 9 세계에서 돌린다(앞 7칸만 넣는다, probe_v2.obs_take)."""
    return add_wrap(spec, {"factory": "probe_v2:obs_take", "dims": list(range(7))})


def supply_need(cfg, seed: int) -> tuple[float, float]:
    """(먹이 공급 상한 Σ_셀 r_c·cap0_c, 기초 수요 N·energy_drain/food_energy_per_unit) — 세계 시드 하나."""
    w = World(cfg, seeds=[int(seed)])
    supply = float((w.regen_field * w.food_cap).sum())
    need = float(w.N * cfg.energy_drain / cfg.food_energy_per_unit)
    return supply, need


def is_food_scarce(cfg, seed: int) -> tuple[bool, float, float]:
    s, n = supply_need(cfg, seed)
    return s < n, s, n
