"""V2 기능 스위치와 기능별 난수 스트림 (계획서 4.8, 0-1b).

버전 설정(`configs/v2.yaml`, `configs/v2_0b.yaml`, `configs/v2_1.yaml`, `configs/v2_2.yaml`, `configs/v2_2r_*.yaml` ...)의
`features:` 아래에 기능마다
블록 하나를 둔다.

    features:
      food_v: {enabled: true, alpha: 0.5, floor: 0.1, recovery_half_lives: [300, 700], init_frac: [0.3, 1.0]}
      daynight: {enabled: false}

- 블록이 없거나 `enabled` 가 없는 기능은 꺼진 것이다. 모두 끄면 env_v2 World 는 v1 과 같은 세계다.
- 블록의 나머지 키는 그 기능의 계수다(`Features.params`). **켠 기능의 계수는 yaml 에 모두 적는다.**
  구현 코드는 기본값을 두지 않고 `p["alpha"]` 처럼 읽는다. 그래야 보정한 값이 설정 파일, 진단 캐시 키
  (`diagnose_v2.py` config_digest), 학습 메타 JSON 에 그대로 남는다.
- 읽을 때 바로 실패하는 것(켰다고 적었는데 아무 일도 안 일어나는 실험을 막는다):
  등록부(`FEATURE_IDS`)에 없는 이름, 블록이 아닌 값, bool 이 아닌 `enabled`, 문자열이 아닌 키,
  숫자처럼 보이는 문자열 값(PyYAML 은 `1e-3`·`1.0e3` 을 문자열로 읽는다. 소수점과 지수 부호를 넣어
  `1.0e-3`·`1.0e+3` 으로 쓴다),
  아직 구현하지 않은 기능 켜기, 구현한 기능(`PARAM_KEYS`)의 모르는 계수 키(`enable`·`alhpa` 같은 오타),
  켠 기능의 빠진 계수.

기능마다 난수 스트림이 따로다: `np.random.default_rng([seed, STREAM_DOMAIN, FEATURE_IDS[name], part])`.
기능 A 를 켜고 끄든, A 가 난수를 몇 개 뽑든 기능 B 의 스트림이 내는 난수열은 그대로이고, 기능 스트림을
써도 v1 스트림(`default_rng(seed)`)은 소비되지 않는다. (A 가 세계를 바꾸면 사망·리스폰 같은 사건이
달라져 B 와 v1 이 난수를 *언제 몇 개* 쓰는지는 달라진다. 그건 기능을 켠 결과다.) 기능을 구현할 때 지킬 것:

1. 기능은 자기 스트림(`World.feature_rng(name, part)`)에서만 뽑는다. v1 스트림 `World.rng` 와
   다른 기능의 스트림에서 뽑지 않는다. 다른 기능의 스트림을 만들지 않는지는 `tests/test_features_v2.py` 가
   구현된 기능마다 확인한다. v1 스트림을 쓰지 않는지는 테스트로 잡히지 않으므로 리뷰로 지킨다.
2. v1 난수 호출을 대신하는 기능(예: v2.5a 리스폰 위치, v2.7 b)도 v1 호출은 그대로 두고 결과만 덮어쓴다.
   그래야 같은 사건이 일어나면 v1 스트림의 위치가 기능 스위치와 상관없이 같다.
3. 이미 있는 기능에 나중에 난수를 더할 때는 새 `part` 번호에서 뽑는다. 같은 스트림 뒤에 붙이면
   앞 버전 세계의 난수열이 밀린다.
4. 번호는 한번 정하면 바꾸지 않는다. 바꾸면 같은 시드의 세계가 조용히 달라진다. 새 기능은 새 번호를 받는다.
5. 이미 있는 기능에 동작을 더할 때는 새 계수 키를 `PARAM_KEYS` 에 더하고, 그 키의 '끔' 값이 앞 버전
   동작이 되게 한다. 앞 버전 설정에는 그 값을 적는다(계수가 빠지면 읽을 때 실패한다). 3 과 5 가 함께
   있어야 "새 기능만 끈 상태 = 직전 버전" 회귀가 지켜진다.

numpy `SeedSequence` 는 시드 목록 끝의 0 을 무시하고(`[s, 2, 7]` 과 `[s, 2, 7, 0]` 이 같은 스트림),
2^32 이상의 정수는 uint32 단어 여러 개로 쪼갠다. 그래서 시드와 part 는 [0, 2^32) 로 제한한다. 이 범위에서
`part=0` 은 계획서의 `[seed, 2, feature_id]` 와 같다. 기능 번호 0 은 쓰지 않는다(`[s, 2, 0]` 은 예전 공용
스트림 `[s, 2]` 와 같아진다). `env_v2/rollout.py` 의 순열 스트림은 둘째 칸이 101·202 라 겹치지 않는다.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

# 시드 목록 둘째 칸. v1 스트림은 default_rng(seed) = [seed, 0, ...] 이고 순열 대조군은 101·202 다.
STREAM_DOMAIN = 2
_U32 = 2**32

# 기능 이름 → 스트림 번호. 버전 순서로 붙였다 (계획서 4.1, 4.9). 번호를 바꾸거나 다시 쓰지 않는다.
# 기능 하나 = 버전 하나의 스위치다. 그 버전을 끄면 직전 버전 세계가 된다.
FEATURE_IDS: Mapping[str, int] = MappingProxyType({
    "food_v": 1,        # v2.0b 먹이 2층: 식생 용량 V 의 훼손과 느린 회복
    "speed": 2,         # v2.1 보행 3단(정지·걷기·뛰기), 대사·섭식 연동
    "vigilance": 3,     # v2.2 경계, threat_recency, 위협 방향
    "regions": 4,       # v2.3 A/B 지역, 소속, 지역 포식자, 지역 기억, 플레이어형 위협
    "daynight": 5,      # v2.4 낮밤 위상, 밤 탐지·섭식·휴식 배수
    "region_env": 6,    # v2.5a 지역 환경: 리스폰 위치 규칙, 지역 재생비, 지역 사이 틈
    "migration": 7,     # v2.5b 이주 조향 항, 지역 먹이·안전 관측, 고갈 안전망
    "weather": 8,       # v2.6 맑음↔비 Markov, 탐지·재생·회복 배수
    "boldness": 9,      # v2.7 개체 대담함 b, 사망 보상 조건화
    "water": 10,        # v2.8 물웅덩이, 수분, 마시기
    "boundary": 11,     # R1 (i) 언리얼 경계 반발 파리티
    "obstacles": 12,    # R1 (ii) 원형 장애물 반발
    "vigil_window": 13,  # v2.2r 경계 재설계(10-03 R2): 경계 행동 열 유무, 창 안 한정 경계(W′), 반사 돌아보기(L)
})

# 구현을 마친 기능. 기능을 구현하는 커밋에서 이름을 더한다.
IMPLEMENTED: frozenset[str] = frozenset({"food_v", "speed", "vigilance", "vigil_window", "daynight"})

# 구현한 기능의 계수 키. 켜면 모두 적어야 하고, 여기 없는 키는 오타로 보고 실패한다.
# 기능을 구현하는 커밋에서 IMPLEMENTED 와 함께 더한다. 값의 범위는 기능 코드가 검사한다.
PARAM_KEYS: Mapping[str, frozenset[str]] = MappingProxyType({
    # v2.0b (env_v2/world.py `_food_v_params`): 훼손 계수 α, 하한(cap0 비율), 휴식 회복 반감기 목록(스텝,
    # reset 마다 하나), V 초기값 cap0 비율 범위 [하, 상](reset 마다 좌우 절반에 하나씩)
    "food_v": frozenset({"alpha", "floor", "recovery_half_lives", "init_frac"}),
    # v2.1 (env_v2/world.py `_speed_params`): 행동 idx 4 의 보행 문턱 [걷기, 뛰기], 상태별 속력 [정지, 걷기,
    # 뛰기](× herb_speed, 정지는 0), 상태별 섭식 배수(want 에 곱한다), 대사 계수 c_rest·c_move
    # (drain = energy_drain·(c_rest + c_move·(v/herb_speed)²)), 에너지 보상을 순변화로 볼지(#4, false = v1 획득량)
    "speed": frozenset({"thresholds", "gait_speed", "gait_eat", "c_rest", "c_move", "net_energy_reward"}),
    # v2.2 (env_v2/world.py `_vigil_params`): 행동 vigilance 의 경계 문턱(a > threshold 면 경계), threat_recency 의
    # 스텝당 감쇠 계수(안 보이면 r ← decay·r), 경계 중 섭식 배수(want 에 곱한다, 4.4 표는 0), 경계 중 시야 각(도,
    # 360 = 모든 방향. 반경은 see_r 그대로, #5). 경계 중 속력 0·대사(speed 의 정지 대사)는 계수가 아니라 규칙이다.
    # threat_flee(10-03, 1-5 Gate E2b 의 10절 #18 변형용): 포식자가 안 보일 때 조향에 더하는 위협 반대 항
    # threat_flee·flee_weight·threat_recency·(−ThreatDir) 의 배수. 0 = 끔(1-4 구현 그대로, 규칙 5)
    "vigilance": frozenset({"threshold", "decay", "eat_mult", "fov_deg", "threat_flee"}),
    # v2.2r (env_v2/world.py `_window_params`, 10-03 R2·수정 제안서 3.1 (나)): vigilance 위에 얹는 스위치라 vigilance 를
    # 함께 켜야 한다. action = 경계 행동 열이 있나(false 면 관측 8·threat_recency 는 그대로 두고 행동 열만 뺀다 — T1·L),
    # window_only = 경계가 '창 안'(결정 때 포식자 안 보임 & threat_recency > theta)에서만 효력이 있나(W′),
    # look_back = 반사 돌아보기(정지 중이고 창 안이면 heading ← ThreatDir, L), theta = 창 문턱(Gate E2 의 θ 0.5).
    # 기능을 끄면(블록이 없으면) v2.2 그대로다 — vigilance 계수 키를 늘리지 않아 configs/v2_2.yaml 의 config_digest
    # (efc8f775f1e1)와 기록된 결과가 그대로 남는다(규칙 5 대신 새 기능 번호, 규칙 4)
    "vigil_window": frozenset({"action", "window_only", "look_back", "theta"}),
    # v2.4 (env_v2/world.py `_daynight_params`, 계획서 4.9.2·4.2·#21): speed 를 함께 켜야 한다. periods = 하루 길이 T
    # 목록(스텝, 짝수, reset 마다 하나), twilight = 전환 앞뒤 박명 폭(T 비율, 계획서 0.05), detect_night·eat_night·
    # rest_night = 어둠 d 에서 포식자 탐지 반경·섭식·정지 비경계 개체의 휴식 대사에 곱하는 (1 − x·d) 의 x(0 = 그 밤 효과
    # 끔, #21 이 Gate N 에서 실패한 항을 0 으로 뺀다), fixed_day_frac = 낮 고정 세계 비율(#27 기능 꺼진 세계, 1.0 이면
    # 모든 세계가 낮 = v2.1 동역학), transition_norm = 관측 to_transition 의 분모(계약 상수 900), start_induce = 시작
    # 상태 유도 비율(탐침 실패 때의 대응 1회, 0 = 끔: reset 의 해 질 녘 시작·낮은 에너지와 리스폰의 낮은 에너지)
    "daynight": frozenset({"periods", "twilight", "detect_night", "eat_night", "rest_night", "fixed_day_frac",
                           "transition_norm", "start_induce"}),
})


@dataclass(frozen=True)
class Features:
    """검증을 마친 `features:` 블록. 등록된 이름만 들어 있다."""

    blocks: Mapping[str, Mapping[str, Any]]

    def enabled(self, name: str) -> bool:
        _check_name(name)
        return bool(self.blocks.get(name, {}).get("enabled", False))

    def params(self, name: str) -> dict[str, Any]:
        """`enabled` 를 뺀 블록의 나머지 키. 깊은 사본이라 고쳐도 설정과 다른 세계에 번지지 않는다."""
        _check_name(name)
        return copy.deepcopy({k: v for k, v in self.blocks.get(name, {}).items() if k != "enabled"})

    @property
    def active(self) -> tuple[str, ...]:
        """켜진 기능 이름을 번호 순으로."""
        return tuple(n for n in FEATURE_IDS if self.enabled(n))

    def __reduce__(self):
        # MappingProxyType 은 pickle 이 안 된다. World 를 deepcopy·pickle 할 수 있게 보통 dict 로 넘겨
        # 다시 만든다. 이미 검증한 값이라 다시 검증하지 않는다(받는 쪽의 IMPLEMENTED 와 무관하게 복원).
        return (_rebuild_features, ({k: copy.deepcopy(dict(v)) for k, v in self.blocks.items()},))


def _freeze(blocks: Mapping[str, Mapping[str, Any]]) -> Features:
    return Features(MappingProxyType({k: MappingProxyType(dict(v)) for k, v in blocks.items()}))


def _rebuild_features(blocks: Mapping[str, Mapping[str, Any]]) -> Features:
    return _freeze(blocks)


def _check_name(name: str) -> None:
    if name not in FEATURE_IDS:
        raise KeyError(f"등록되지 않은 V2 기능 '{name}'. 등록된 기능: {', '.join(FEATURE_IDS)}")


def _check_part(part: Any) -> None:
    if isinstance(part, bool) or not isinstance(part, (int, np.integer)) or not 0 <= part < _U32:
        raise ValueError(f"part 는 0 이상 2^32 미만의 정수여야 한다. 받은 값: {part!r}")


def _looks_numeric(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        float(v)
    except ValueError:
        return False
    return True


def _check_values(name: str, key: str, v: Any) -> None:
    items = v if isinstance(v, (list, tuple)) else [v]
    for x in items:
        if _looks_numeric(x):
            raise ValueError(
                f"features.{name}.{key} 의 값 {x!r} 가 문자열이다. PyYAML 은 '1e-3'·'1.0e3' 같은 지수 "
                f"표기를 문자열로 읽는다. 소수점과 지수 부호를 넣어 1.0e-3, 1.0e+3 처럼 쓴다"
            )


def parse_features(raw: Mapping[str, Any] | None, implemented: frozenset[str] | None = None,
                   param_keys: Mapping[str, frozenset[str]] | None = None) -> Features:
    """`cfg.v2["features"]` 를 검증한다. 형식이 틀리면 ValueError, 모르는 이름이면 KeyError.

    `implemented`·`param_keys` 를 주지 않으면 이 모듈의 `IMPLEMENTED`·`PARAM_KEYS` 를 그때그때 읽는다
    (테스트에서 바꿀 수 있게).
    """
    if implemented is None:
        implemented = IMPLEMENTED
    if param_keys is None:
        param_keys = PARAM_KEYS
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"features 는 기능 이름 → 블록(dict) 이어야 한다. 받은 값: {raw!r}")
    blocks: dict[str, Mapping[str, Any]] = {}
    for name, block in raw.items():
        _check_name(name)
        if block is None:
            block = {}
        if not isinstance(block, Mapping):
            raise ValueError(
                f"features.{name} 는 {{enabled: true|false, ...}} 꼴의 블록이어야 한다. 받은 값: {block!r}"
            )
        for key, v in block.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"features.{name} 의 키는 문자열이어야 한다(YAML 1.1 에서 on/yes/off 는 bool 이다). "
                    f"받은 키: {key!r}"
                )
            if key != "enabled":
                _check_values(name, key, v)
        on = block.get("enabled", False)
        if not isinstance(on, bool):
            raise ValueError(f"features.{name}.enabled 는 true/false 여야 한다. 받은 값: {on!r}")
        if on and name not in implemented:
            raise ValueError(
                f"V2 기능 '{name}' 은 아직 구현되지 않았다. 켜도 세계가 바뀌지 않으므로 끈 채로 둔다 "
                f"(구현된 기능: {', '.join(sorted(implemented)) or '없음'})"
            )
        if name in implemented:
            known = param_keys.get(name, frozenset())
            unknown = sorted(set(block) - {"enabled"} - set(known))
            if unknown:
                raise ValueError(
                    f"features.{name} 에 모르는 키 {unknown} 가 있다(오타?). 쓸 수 있는 키: "
                    f"enabled, {', '.join(sorted(known)) or '(계수 없음)'}"
                )
            missing = sorted(set(known) - set(block))
            if on and missing:
                raise ValueError(
                    f"features.{name} 을 켜려면 계수 {missing} 를 적어야 한다. 계수는 yaml 이 유일한 원본이다"
                )
        blocks[name] = dict(block)
    return _freeze(blocks)


def features_of(cfg) -> Features:
    """설정 객체에서 기능 블록을 읽는다. v1 Config 처럼 `v2` 가 없으면 모두 꺼진 것으로 본다."""
    v2 = getattr(cfg, "v2", None) or {}
    return parse_features(v2.get("features"))


def feature_stream(seed: int, name: str, part: int = 0) -> np.random.Generator:
    """세계 시드 `seed` 에서 기능 `name` 의 `part` 번 난수 스트림을 만든다."""
    _check_name(name)
    _check_part(part)
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or not 0 <= seed < _U32:
        raise ValueError(f"seed 는 0 이상 2^32 미만의 정수여야 한다. 받은 값: {seed!r}")
    return np.random.default_rng([int(seed), STREAM_DOMAIN, FEATURE_IDS[name], int(part)])
