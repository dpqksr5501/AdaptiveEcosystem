"""v3 행동 레퍼토리 — 행동 실행기, 잠금·사건, 개체 행동 상태 (R0 명세 `Docs/RL_Policy/RL_V3_R0_SPEC.md` 2·3절).

기능 `repertoire`(번호 15)를 켠 세계는 행동이 한 열 'behavior' 다(값 = 정수 행동 번호를 float 로. 정수가 아니면 `World` 가
거부한다 — 연속 정책의 (0, 1) 출력이 조용히 GRAZE 가 되지 않게). 정책은 매 스텝 원하는 행동(요청)을 내고, 실행기가 결정
시점에만 요청을 받아들인다. 고른 행동은 아래 제어기가 속도·보행·섭식·대사·지각으로 바꾼다.
이 파일은 세계와 무관한 순수 계산이다(`World` 가 기하 입력을 넘기고 결과를 쓴다). 난수를 쓰지 않는다.

행동 번호 (계약 — 한 번 정한 뜻을 바꾸지 않는다. 언리얼 `EEcoBehavior` 와 같은 순서):
  0 GRAZE 먹기, 1 FLEE 도주, 2 HIDE 숨기, 3 FREEZE 얼기, 4 SLEEP 잠
위상 `phase`: 0 진입, 1 지속, 2 이탈(SLEEP 의 기상만 이탈 위상을 쓴다)
  GRAZE·FREEZE: 행동 첫 스텝 0, 그 뒤 1. FLEE: 놀람 정지 중(또는 놀람이 없으면 첫 스텝) 0, 그 뒤 1.
  HIDE: 은신처로 가는 중 0, 도착해 웅크리면 1. SLEEP: 진입 sleep_enter 스텝 0, 수면 1, 기상 2.

개체 상태 (`RepState`, 개체마다 하나. 언리얼 FEcoBehaviorStateFragment 의 거울):
  behavior, phase, steps_in(행동 경과 스텝, 진입 스텝 0), seq(행동이 바뀔 때마다 +1, mod 256 — C++ uint8),
  lock_left(남은 잠금, ≤ 0 이면 결정 시점), startle_left(남은 놀람 정지), waking·wake_left·wake_target(기상 중·남은 기상·
  기상 뒤 행동), wake_ev(기상 중에 사건이 났다), ev_wait(대기 중인 사건 결정까지 남은 스텝, −1 = 없음),
  hide_target(HIDE 가 고른 은신처 색인, 없으면 −1), arrived(HIDE 도착), 사건 기준값 prev_pc·prev_near·prev_fast·prev_low·
  prev_dark(결정 여부와 무관하게 스텝마다 그 스텝의 결정 관측 값으로 갱신한다), away(마지막 위협 반대 방향, 단위벡터. 본 적
  없으면 0), recency(threat_recency), jitter(개체별 사건 결정 지연, 개체가 새로 날 때마다 다시 정한다).

한 스텝 순서 (`World.step` 이 부른다. C++ 로 옮길 때 이 순서를 지킨다):
  A) `arbitrate` — 결정 때 관측(이전 스텝 끝 기하)으로
     a. HIDE 도착: HIDE·미도착·은신처 안이면 도착, lock_left ← lock_hide. 진입 스텝이 아니면 사건 E6
     b. 사건: E1 보이는 위협 수가 직전 스텝보다 많다, E2 가장 가까운 보이는 위협이 event_near 안으로 들어옴 또는 접근 관측이
        event_approach 이상이 됨(둘 다 안 → 밖 경계 넘기), E3 SLEEP 중 위협이 보임, E4 에너지가 event_energy 아래로 내려감,
        E5 어둠 d 가 event_dark 를 지남(양방향), E6 위 a.
        E1·E2 는 '사건 비교 시야'(이번 관측과 직전 관측의 행동 시야 배수 중 작은 쪽, `World._geometry` 의 *_ev)로 센 값을
        직전 기준값과 비교한다 — 자기 행동이 바뀌어 시야가 넓어진 것(GRAZE 고개 숙임 0.6 → FREEZE 1.0, SLEEP 0.3 → 기상 뒤)
        만으로 생긴 위협은 사건이 아니다(넓어진 띠의 위협은 기준값에만 들어간다). 기준값은 실제 관측(지금 시야) 값으로 둔다.
        E1 은 수의 증가라 같은 스텝에 하나가 나가고 하나가 들어오면 사건이 아니다(C++ 도 같게 둔다).
     c. 지연: 대기 사건이 없는 개체에 사건이 나면 ev_wait ← jitter. ev_wait = 0 인 개체가 이번 스텝의 사건 결정(fire)이다.
        나머지 대기는 1 줄인다
     d. 기상 끝: 기상 중(깨는 스텝 포함)에 난 사건은 결정 지연과 무관하게 wake_ev 로 남긴다. 기상 중이고 wake_left ≤ 0 이면
        기상이 끝난다. wake_ev 가 있으면 이 스텝이 결정 시점이고 기상 뒤 행동 = 지금 요청(SLEEP 이면 처음 기상 요청
        wake_target), 없으면 wake_target 이다. 깨는 스텝은 대기 사건을 지운다(ev_wait ← −1) — 기상 중에 위협이 나타나도 깨는
        스텝에 바로 반응한다(사건이 결정 없이 사라지지 않고, 깨자마자 GRAZE 잠금·놀람에 묶이지 않는다)
     e. 결정 = (lock_left ≤ 0 또는 fire) & 기상 중 아님 & 이번 스텝에 깨지 않음. 결정 시점은 대기 사건을 쓴다(ev_wait ← −1).
        요청 ≠ 지금 행동이면: SLEEP 은 기상(이탈 위상, sleep_wake 스텝 동안 정지)을 시작하고 기상 뒤 요청으로 바꾼다.
        그 밖은 곧바로 바꾼다. 요청 = 지금 행동이면 그대로다(잠금을 새로 걸지 않는다 — 잠금이 끝난 뒤에는 스텝마다 결정 시점)
     f. 진입(`_enter`): behavior ← 새 행동, seq + 1, steps_in ← 0, 잠금(GRAZE lock_graze, FLEE lock_flee, HIDE
        hide_travel_max, FREEZE lock_freeze, SLEEP sleep_enter + sleep_hold), GRAZE → FLEE 면 startle_left ← startle_steps
        (FREEZE·HIDE → FLEE 는 0, SLEEP → FLEE 는 기상이 지연이다), HIDE 면 가장 가까운 은신처(동점이면 낮은 색인, 없으면 −1)를
        고르고 이미 은신처 안이면 곧바로 도착(lock_hide, E6 없음)
     g. 위상
  B) `control` — 행동별 제어기 (G 먹이 기울기, C 무리 중심, Sep 분리, A 위협 반대, T 고른 은신처 쪽, n = 정규화)
     GRAZE  방향 n(graze_forage·G + graze_cohesion·C + sep_weight·Sep). 지금 셀 먹이 ≥ graze_eat_min 이면 정지(머리 숙여
            먹기), 아니면 걷기. 섭식 gait_eat[보행](정지 1.0, 걷기 0.5). 자기 포식자 탐지 반경 × graze_head_down(M5)
     FLEE   방향 n(flee_weight·A + graze_cohesion·C + sep_weight·Sep), A 는 위협이 보이면 가장 가까운 위협 반대, 안 보이면
            마지막 A. 뛰기. 놀람 중이면 정지(M2). 섭식 0
     HIDE   도착 전: 방향 n(T + sep_weight·Sep), 위협이 보이면 뛰기 아니면 걷기. 고른 은신처가 없으면(세계에 은신처가 없다)
            정지. 도착: 정지·웅크림. 섭식 0
     FREEZE 정지, heading ← 위협 쪽(보이면 가장 가까운 위협, 아니면 마지막 위협 방향, 모르면 그대로). 섭식 0
     SLEEP  정지(진입·수면·기상 모두). 섭식 0. 자기 탐지 반경 × sleep_sight
     방향이 없으면(|v| ≤ EPS) 보행은 정지다(v2.1 규칙). 속도 = n(방향)·herb_speed·gait_speed[보행].
     대사 배수 = drain_mult[보행] × (SLEEP 이고 결정 때 은신처 안이면 1 − sleep_rest·d — 휴식 할인은 SLEEP 전용).
     정지(still, M1): FREEZE, 도착 HIDE, SLEEP. 웅크림(crouch, M6): 도착 HIDE.
  C) (World) 이동·포식자·섭식·대사. 대사 = energy_drain × 대사 배수, 섭식 = 섭식 배수 × (1 − eat_night·d).
     포식자·위협의 표적 선택 체감 거리 = 실거리 × max(은신 배수, still 이면 c_still), 은신 배수 = 은신처 안이면 행동별 값
     (웅크린 HIDE cover_mult_crouch, GRAZE cover_mult_graze, SLEEP cover_mult_sleep, 그 밖(FLEE·FREEZE·가는 중 HIDE)
     cover_mult_other — 넷 다 yaml 계수), 밖이면 1. 포획 판정 거리 = 실거리 × 은신 배수(c_still 없음).
  D) `tick` — steps_in + 1, lock_left − 1, startle_left·wake_left − 1(0 에서 멈춤)
  E) (World) 관측. `perceive` 가 away·recency 를 갱신한다(보이면 away ← 가장 가까운 위협 반대, recency ← 1, 아니면
     recency ← recency_decay·recency).

파리티 메모 (C++ 이식):
  - 스텝 뒤 훅 `World.beh_steps` 는 tick 전 값(이번 스텝에 실행한 행동의 경과)이고, 관측 obs_extra 의 beh_steps 칸은 tick 뒤
    값(다음 결정 때 경과)이라 같은 스텝의 훅보다 1 크다(최대 steps_norm 에서 자른 비율).
  - 사건 결정 지연 jitter = H(505, 세계 시드, 개체 키) mod (J + 1). 개체 키 = 슬롯·2^32 + 세대(그 슬롯의 리스폰 횟수,
    env_v2/rollout.py `hold_agent_keys` 와 같은 꼴). C++ 는 (세션 시드, AgentKey) — AgentKey 가 리스폰마다 새 값이듯 파이썬도
    리스폰마다 세대가 바뀌어 지연을 다시 정한다.
  - FLEE 의 대사는 실제 보행을 따른다 — 놀람 정지 중에는 정지 대사(명세 표의 '뛰기 대사'는 달리는 동안이다, PREREG 변경 기록).

C++ 꼴 (엔진 무관 헤더 EcoBehaviorArbiter.h·EcoBehaviorControllers.h 의 거울):
  // Arbitrate(State, Request, Obs) — 개체 하나. Obs.*Ev = 사건 비교 시야(위 b)로 센 값
  if (S.Behavior == Hide && !S.bArrived && Obs.bInCover) { S.bArrived = true; S.Lock = LockHide; bE6 = S.StepsIn > 0; }
  bEvent = Obs.PredCountEv > S.PrevPc || (bNearEv && !S.bPrevNear) || (bFastEv && !S.bPrevFast)
           || (S.Behavior == Sleep && Obs.PredCount > 0) || (bLow && !S.bPrevLow) || (bDarkSide != S.bPrevDark) || bE6;
  S.PrevPc = Obs.PredCount; S.bPrevNear = bNear; S.bPrevFast = bFast; S.bPrevLow = bLow; S.bPrevDark = bDarkSide;
  if (bEvent && S.EvWait < 0) S.EvWait = Jitter;  bFire = S.EvWait == 0;  if (S.EvWait > 0) --S.EvWait;
  if (S.bWaking && bEvent) S.bWakeEv = true;
  bWoke = S.bWaking && S.WakeLeft <= 0;  bWakeDecide = bWoke && S.bWakeEv;
  if (bWoke) Enter(S, bWakeDecide && Request != Sleep ? Request : S.WakeTarget);
  bDecide = (S.Lock <= 0 || bFire) && !S.bWaking && !bWoke;  if (bFire || bDecide || bWoke) S.EvWait = -1;
  if (bDecide && Request != S.Behavior) { if (S.Behavior == Sleep && SleepWake > 0) { S.bWaking = true; S.bWakeEv = false;
      S.WakeLeft = SleepWake; S.WakeTarget = Request; } else Enter(S, Request); }      // Enter 는 bWaking·bWakeEv 를 끈다
  // 스텝 끝: ++S.StepsIn; --S.Lock; S.Startle = max(S.Startle - 1, 0); S.WakeLeft = max(S.WakeLeft - 1, 0);
  Jitter = Mix64Chain(0, JITTER_TAG, Seed, AgentKey) % (J + 1)   (env_v2/rollout.py 유지 표본 해시와 같은 SplitMix64 사슬)
  // SteerBehavior(G, S, Cfg) — 개체 하나. A = bSeen ? AwayFromPred : S.Away
  FVector Raw = 0; int Gait = Stop; float Eat = 0, See = 1; bool bCrouch = false;
  switch (S.Behavior) {
    case Graze:  Raw = Forage*FoodGrad + Coh*ToCentroid + SepW*Separation; Gait = bFoodOk ? Stop : Walk;
                 Eat = GaitEat[Gait]; See = HeadDown; break;
    case Flee:   Raw = FleeW*A + Coh*ToCentroid + SepW*Separation; Gait = S.Startle > 0 ? Stop : Run; break;
    case Hide:   if (S.bArrived) bCrouch = true;
                 else if (S.HideTarget >= 0) { Raw = ToTarget + SepW*Separation; Gait = bSeen ? Run : Walk; } break;
    case Freeze: if (!A.IsZero()) Facing = -A; break;
    case Sleep:  See = SleepSight; break; }
  if (Raw.SizeSquared() <= EPS*EPS) Gait = Stop;   Velocity = Raw.GetSafeNormal() * HerbSpeed * GaitSpeed[Gait];
  DrainMult = GaitDrain[Gait] * (S.Behavior == Sleep && bInCover ? 1 - SleepRest*D : 1);
  bStill = S.Behavior == Freeze || S.Behavior == Sleep || bCrouch;   // 포식자 표적 체감 거리 × max(은신 배수, CStill)
  CoverMult = bCrouch ? CoverCrouch : S.Behavior == Graze ? CoverGraze : S.Behavior == Sleep ? CoverSleep : CoverOther;
"""

from __future__ import annotations

import math

import numpy as np

from .steering import EPS, normalize

GRAZE, FLEE, HIDE, FREEZE, SLEEP = 0, 1, 2, 3, 4
N_BEHAVIORS = 5
BEHAVIOR_NAMES = ("graze", "flee", "hide", "freeze", "sleep")
PHASE_ENTER, PHASE_ACTIVE, PHASE_EXIT = 0, 1, 2
SEQ_MOD = 256                   # C++ uint8 Seq
# 보행 번호 (world.GAIT_* 와 같다. 순환 import 를 피해 여기에 다시 적는다)
_STOP, _WALK, _RUN = 0, 1, 2
# 사건 결정 지연 해시의 첫 입력(스트림 구분값). rollout._SALT(101·202·303·404)와 겹치지 않는다
JITTER_TAG = 505
# 관측 obs_extra 칸 이름 (순서 = 관측 열 순서)
OBS_EXTRA_NAMES = ("pred_approach", "kin_alarm", "beh_graze", "beh_flee", "beh_hide", "beh_freeze", "beh_sleep",
                   "beh_steps", "threat_recency")

_GOLDEN = 0x9E3779B97F4A7C15
_M1, _M2 = 0xBF58476D1CE4E5B9, 0x94D049BB133111EB

_INT_KEYS = ("lock_graze", "lock_flee", "lock_freeze", "lock_hide", "hide_travel_max", "sleep_enter", "sleep_hold",
             "sleep_wake", "startle_steps", "decision_jitter")
# 은신 배수(M6, 은신처 안일 때 행동별). 체감 거리를 늘리기만 한다(≥ 1)
COVER_KEYS = ("cover_mult_crouch", "cover_mult_graze", "cover_mult_sleep", "cover_mult_other")


def _mix64(z: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        z = z ^ (z >> np.uint64(30))
        z = z * np.uint64(_M1)
        z = z ^ (z >> np.uint64(27))
        z = z * np.uint64(_M2)
        return z ^ (z >> np.uint64(31))


def mix_chain(*xs) -> np.ndarray:
    """H(x_1, ..., x_n) = SplitMix64 사슬 (env_v2/rollout.py `hold_hash` 와 같은 식). 배열은 브로드캐스트한 uint64."""
    h = np.zeros((), dtype=np.uint64)
    with np.errstate(over="ignore"):
        for x in xs:
            h = _mix64((h ^ np.asarray(x).astype(np.uint64)) + np.uint64(_GOLDEN))
    return h


def agent_keys(slots, generations) -> np.ndarray:
    """개체 키 = 슬롯·2^32 + 세대 (uint64, env_v2/rollout.py `hold_agent_keys` 와 같은 꼴)."""
    return ((np.asarray(slots).astype(np.uint64) << np.uint64(32))
            + np.asarray(generations).astype(np.uint64))


def decision_jitter(seed: int, slots, generations, j_max: int) -> np.ndarray:
    """개체의 사건 결정 지연 H(505, 세계 시드, 개체 키) mod (J + 1) ∈ [0, J] (int64). 세계 시드를 넣어 같은 슬롯도
    세계마다 지연이 다르고(침입 시험의 고정 슬롯이 시드마다 같은 지연을 갖지 않는다), 세대를 넣어 리스폰한 개체는 지연을
    새로 받는다(C++ AgentKey 와 같은 뜻)."""
    slots = np.asarray(slots, dtype=np.int64)
    if j_max <= 0:
        return np.zeros(slots.shape, dtype=np.int64)
    h = mix_chain(JITTER_TAG, np.int64(seed), agent_keys(slots, generations))
    return (h % np.uint64(j_max + 1)).astype(np.int64)


def _num(key, x) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) or not math.isfinite(x):
        raise ValueError(f"features.repertoire.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
    return float(x)


def parse_params(p: dict, f) -> dict:
    """repertoire 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다.

    - 정수(스텝) ≥ 0: lock_graze·lock_flee·lock_freeze·lock_hide·hide_travel_max·sleep_enter·sleep_hold·sleep_wake·
      startle_steps·decision_jitter
    - c_still·cover_mult_crouch·cover_mult_graze·cover_mult_sleep·cover_mult_other ≥ 1 (체감 거리를 늘리기만 한다)
    - graze_head_down·sleep_sight ∈ (0, 1], sleep_rest·event_approach·event_energy·recency_decay ∈ [0, 1],
      event_dark ∈ (0, 1), event_near > 0, steps_norm > 0, graze_eat_min·graze_forage·graze_cohesion ≥ 0
    - obs_extra (bool)
    speed·daynight 를 함께 켜야 하고(보행 속력·섭식·대사표와 어둠 d 를 쓴다) vigilance 와 함께 켤 수 없다(행동 열이 하나다).
    """
    if not f.enabled("speed") or not f.enabled("daynight"):
        raise ValueError("features.repertoire 는 speed·daynight 를 함께 켜야 한다(v3 는 v2.4s 위의 버전이다)")
    if f.enabled("vigilance"):
        raise ValueError("features.repertoire 는 vigilance 와 함께 켤 수 없다(행동이 'behavior' 한 열이다)")
    out = {}
    for k in _INT_KEYS:
        x = p[k]
        if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x < 0:
            raise ValueError(f"features.repertoire.{k} 는 0 이상의 정수(스텝)여야 한다. 받은 값: {x!r}")
        out[k] = int(x)
    for k in ("c_still",) + COVER_KEYS:
        x = _num(k, p[k])
        if x < 1.0:
            raise ValueError(f"features.repertoire.{k} 는 1 이상이어야 한다(체감 거리 배수). 받은 값: {x}")
        out[k] = x
    for k in ("graze_head_down", "sleep_sight"):
        x = _num(k, p[k])
        if not 0.0 < x <= 1.0:
            raise ValueError(f"features.repertoire.{k} 는 (0, 1] 이어야 한다. 받은 값: {x}")
        out[k] = x
    for k in ("sleep_rest", "event_approach", "event_energy", "recency_decay"):
        x = _num(k, p[k])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.repertoire.{k} 는 [0, 1] 이어야 한다. 받은 값: {x}")
        out[k] = x
    x = _num("event_dark", p["event_dark"])
    if not 0.0 < x < 1.0:
        raise ValueError(f"features.repertoire.event_dark 는 (0, 1) 이어야 한다. 받은 값: {x}")
    out["event_dark"] = x
    for k in ("event_near", "steps_norm"):
        x = _num(k, p[k])
        if x <= 0.0:
            raise ValueError(f"features.repertoire.{k} 는 양수여야 한다. 받은 값: {x}")
        out[k] = x
    for k in ("graze_eat_min", "graze_forage", "graze_cohesion"):
        x = _num(k, p[k])
        if x < 0.0:
            raise ValueError(f"features.repertoire.{k} 는 0 이상이어야 한다. 받은 값: {x}")
        out[k] = x
    if not isinstance(p["obs_extra"], bool):
        raise ValueError(f"features.repertoire.obs_extra 는 true/false 여야 한다. 받은 값: {p['obs_extra']!r}")
    out["obs_extra"] = p["obs_extra"]
    # 진입 잠금 표 (행동 번호 순). HIDE 는 도착까지의 최대 잠금, SLEEP 은 진입 + 최소 수면이다
    out["locks"] = np.array([out["lock_graze"], out["lock_flee"], out["hide_travel_max"], out["lock_freeze"],
                             out["sleep_enter"] + out["sleep_hold"]], dtype=np.int64)
    return out


def cover_mult(p: dict, behavior: np.ndarray, crouch: np.ndarray) -> np.ndarray:
    """은신처 안일 때의 행동별 은신 배수 (M6, 모듈 docstring C): 웅크린 HIDE cover_mult_crouch, GRAZE cover_mult_graze,
    SLEEP cover_mult_sleep, 그 밖(FLEE·FREEZE·가는 중 HIDE) cover_mult_other."""
    b = np.asarray(behavior)
    return np.where(crouch, p["cover_mult_crouch"],
                    np.where(b == GRAZE, p["cover_mult_graze"],
                             np.where(b == SLEEP, p["cover_mult_sleep"], p["cover_mult_other"])))


class RepState:
    """개체별 행동 상태 (모듈 docstring). 모든 칸이 numpy 배열이라 World 와 함께 pickle·deepcopy 된다.
    `seed` 는 세계 시드(사건 결정 지연 해시, `decision_jitter`). 처음 개체는 모두 세대 0 이다."""

    def __init__(self, n: int, p: dict, energy: np.ndarray, dark: float, seed: int):
        self.behavior = np.full(n, GRAZE, dtype=np.int8)
        self.phase = np.zeros(n, dtype=np.int8)
        self.steps_in = np.zeros(n, dtype=np.int64)
        self.seq = np.zeros(n, dtype=np.int64)
        self.lock_left = np.full(n, p["lock_graze"], dtype=np.int64)
        self.startle_left = np.zeros(n, dtype=np.int64)
        self.waking = np.zeros(n, dtype=bool)
        self.wake_left = np.zeros(n, dtype=np.int64)
        self.wake_target = np.full(n, GRAZE, dtype=np.int8)
        self.wake_ev = np.zeros(n, dtype=bool)
        self.ev_wait = np.full(n, -1, dtype=np.int64)
        self.hide_target = np.full(n, -1, dtype=np.int64)
        self.arrived = np.zeros(n, dtype=bool)
        self.prev_pc = np.zeros(n, dtype=np.int64)
        self.prev_near = np.zeros(n, dtype=bool)
        self.prev_fast = np.zeros(n, dtype=bool)
        self.prev_low = np.asarray(energy, dtype=np.float64) < p["event_energy"]
        self.prev_dark = np.full(n, dark >= p["event_dark"], dtype=bool)
        self.away = np.zeros((n, 2))
        self.recency = np.zeros(n)
        self.jitter = decision_jitter(seed, np.arange(n), np.zeros(n, dtype=np.int64), p["decision_jitter"])

    def reset_slots(self, idx: np.ndarray, p: dict, energy: np.ndarray, dark: float, seed: int,
                    generations: np.ndarray) -> None:
        """리스폰: 새 개체는 GRAZE 진입 상태로 시작한다(seq 는 +1 — 같은 GRAZE 라도 새 개체임을 알린다). 사건 결정 지연은
        새 세대(`generations`, idx 순서)로 다시 정한다."""
        self.behavior[idx] = GRAZE
        self.phase[idx] = PHASE_ENTER
        self.steps_in[idx] = 0
        self.seq[idx] = (self.seq[idx] + 1) % SEQ_MOD
        self.lock_left[idx] = p["lock_graze"]
        self.startle_left[idx] = 0
        self.waking[idx] = False
        self.wake_left[idx] = 0
        self.wake_target[idx] = GRAZE
        self.wake_ev[idx] = False
        self.ev_wait[idx] = -1
        self.hide_target[idx] = -1
        self.arrived[idx] = False
        self.prev_pc[idx] = 0
        self.prev_near[idx] = False
        self.prev_fast[idx] = False
        self.prev_low[idx] = np.asarray(energy, dtype=np.float64) < p["event_energy"]
        self.prev_dark[idx] = dark >= p["event_dark"]
        self.away[idx] = 0.0
        self.recency[idx] = 0.0
        self.jitter[idx] = decision_jitter(seed, idx, generations, p["decision_jitter"])


def _enter(rs: RepState, p: dict, m: np.ndarray, new: np.ndarray, in_cover: np.ndarray, cover_k: np.ndarray) -> None:
    """마스크 `m` 개체를 행동 `new` 로 바꾼다(모듈 docstring A.f)."""
    if not m.any():
        return
    old = rs.behavior.copy()
    nb = np.asarray(new, dtype=np.int8)
    rs.behavior = np.where(m, nb, rs.behavior).astype(np.int8)
    rs.seq = np.where(m, (rs.seq + 1) % SEQ_MOD, rs.seq)
    rs.steps_in = np.where(m, 0, rs.steps_in)
    rs.lock_left = np.where(m, p["locks"][rs.behavior], rs.lock_left)
    startle = m & (rs.behavior == FLEE) & (old == GRAZE)
    rs.startle_left = np.where(m, np.where(startle, p["startle_steps"], 0), rs.startle_left)
    rs.waking = rs.waking & ~m
    rs.wake_ev = rs.wake_ev & ~m
    rs.wake_left = np.where(m, 0, rs.wake_left)
    hide = m & (rs.behavior == HIDE)
    rs.hide_target = np.where(m, np.where(hide, cover_k, -1), rs.hide_target)
    now = hide & in_cover
    rs.arrived = np.where(m, now, rs.arrived)
    rs.lock_left = np.where(now, p["lock_hide"], rs.lock_left)


def arbitrate(rs: RepState, p: dict, request: np.ndarray, obs: dict) -> dict:
    """한 스텝의 결정 (모듈 docstring A). `obs` 는 결정 때 값: pred_count (N,), d_pred_min (N,, 안 보이면 inf),
    pred_approach (N,), energy (N,, max_energy 비율), dark (스칼라 d), in_cover (N,), cover_k (N,, 가장 가까운 은신처, 없으면 −1).
    선택: pred_count_ev·d_pred_min_ev·pred_approach_ev — 사건 비교 시야(모듈 docstring A.b)로 센 값. 없으면 위 값을 쓴다
    (시야가 바뀌지 않은 개체는 둘이 같다).
    반환: 마스크 decide(결정 시점, 사건 결정이 있던 기상 끝 포함), switch(행동이 바뀐 개체), event(사건), fire(사건 결정)."""
    req = np.asarray(request, dtype=np.int64)
    pc = np.asarray(obs["pred_count"], dtype=np.int64)
    in_cover, cover_k = obs["in_cover"], obs["cover_k"]
    # a. HIDE 도착
    arrive = (rs.behavior == HIDE) & ~rs.arrived & in_cover
    rs.arrived = rs.arrived | arrive
    rs.lock_left = np.where(arrive, p["lock_hide"], rs.lock_left)
    e6 = arrive & (rs.steps_in > 0)
    # b. 사건 E1~E5. E1·E2 는 사건 비교 시야로 센 값을 쓰고, 기준값은 실제 관측 값으로 둔다
    seen = pc > 0
    near = seen & (obs["d_pred_min"] < p["event_near"])
    fast = seen & (obs["pred_approach"] >= p["event_approach"])
    pce = np.asarray(obs.get("pred_count_ev", pc), dtype=np.int64)
    seen_e = pce > 0
    near_e = seen_e & (np.asarray(obs.get("d_pred_min_ev", obs["d_pred_min"])) < p["event_near"])
    fast_e = seen_e & (np.asarray(obs.get("pred_approach_ev", obs["pred_approach"])) >= p["event_approach"])
    low = obs["energy"] < p["event_energy"]
    dark = bool(obs["dark"] >= p["event_dark"])
    event = ((pce > rs.prev_pc) | (near_e & ~rs.prev_near) | (fast_e & ~rs.prev_fast)
             | ((rs.behavior == SLEEP) & seen) | (low & ~rs.prev_low) | (rs.prev_dark != dark) | e6)
    rs.prev_pc, rs.prev_near, rs.prev_fast, rs.prev_low = pc.copy(), near, fast, low
    rs.prev_dark = np.full(len(pc), dark, dtype=bool)
    # c. 지연
    rs.ev_wait = np.where(event & (rs.ev_wait < 0), rs.jitter, rs.ev_wait)
    fire = rs.ev_wait == 0
    rs.ev_wait = np.where(rs.ev_wait > 0, rs.ev_wait - 1, rs.ev_wait)
    # d. 기상 끝. 기상 중 사건은(지연이 남았어도) 남겨 두었다가 깨는 스텝을 결정 시점으로 만든다
    rs.wake_ev = rs.wake_ev | (event & rs.waking)
    woke = rs.waking & (rs.wake_left <= 0)
    wake_dec = woke & rs.wake_ev
    _enter(rs, p, woke, np.where(wake_dec & (req != SLEEP), req, rs.wake_target), in_cover, cover_k)
    # e. 결정
    decide = ((rs.lock_left <= 0) | fire) & ~rs.waking & ~woke
    rs.ev_wait = np.where(fire | decide | woke, -1, rs.ev_wait)
    change = decide & (req != rs.behavior)
    to_wake = change & (rs.behavior == SLEEP) if p["sleep_wake"] > 0 else np.zeros_like(change)
    rs.waking = rs.waking | to_wake
    rs.wake_ev = rs.wake_ev & ~to_wake
    rs.wake_left = np.where(to_wake, p["sleep_wake"], rs.wake_left)
    rs.wake_target = np.where(to_wake, req, rs.wake_target).astype(np.int8)
    sw = change & ~to_wake
    _enter(rs, p, sw, req, in_cover, cover_k)
    # g. 위상
    rs.phase = phase_of(rs, p)
    return dict(decide=decide | wake_dec, switch=sw | woke, event=event, fire=fire)


def phase_of(rs: RepState, p: dict) -> np.ndarray:
    """지금 상태의 위상 (모듈 docstring 의 위상 표)."""
    b, s = rs.behavior, rs.steps_in
    ph = np.where(s == 0, PHASE_ENTER, PHASE_ACTIVE)
    ph = np.where((b == FLEE) & (rs.startle_left > 0), PHASE_ENTER, ph)
    ph = np.where(b == HIDE, np.where(rs.arrived, PHASE_ACTIVE, PHASE_ENTER), ph)
    ph = np.where(b == SLEEP, np.where(rs.waking, PHASE_EXIT, np.where(s < p["sleep_enter"], PHASE_ENTER,
                                                                         PHASE_ACTIVE)), ph)
    return ph.astype(np.int8)


def control(rs: RepState, p: dict, inp: dict, cfg, sp: dict) -> dict:
    """행동별 제어기 (모듈 docstring B). `inp`: food_grad·to_centroid·separation·away_from_pred·to_target (N,2),
    pred_count (N,), food_ok (N,) bool(지금 셀 먹이 ≥ graze_eat_min), in_cover (N,) bool·dark(스칼라 d, 결정 때 값).
    `sp` 는 speed 계수(world._speed_params). HIDE 가 고른 은신처가 없으면(rs.hide_target < 0) 정지다.
    반환: vel (N,2), gait (N,) int8, eat (N,) 섭식 배수, drain (N,) 대사 배수(× energy_drain: drain_mult[보행], SLEEP 이고
    은신처 안이면 × (1 − sleep_rest·d)), see (N,) 자기 포식자 탐지 반경 배수, still·crouch (N,) bool, face (N,2) heading
    덮기(0 이면 그대로)."""
    b = rs.behavior
    seen = np.asarray(inp["pred_count"]) > 0
    sep = cfg.sep_weight * inp["separation"]
    coh = p["graze_cohesion"] * inp["to_centroid"]
    away = np.where(seen[:, None], inp["away_from_pred"], rs.away)
    d_graze = p["graze_forage"] * inp["food_grad"] + coh + sep
    d_flee = cfg.flee_weight * away + coh + sep
    d_hide = np.where((rs.hide_target >= 0)[:, None], inp["to_target"] + sep, 0.0)
    is_g, is_f, is_h = b == GRAZE, b == FLEE, b == HIDE
    crouch = is_h & rs.arrived
    raw = np.where(is_g[:, None], d_graze, np.where(is_f[:, None], d_flee,
                                                    np.where((is_h & ~crouch)[:, None], d_hide, 0.0)))
    has_dir = (raw * raw).sum(1) > EPS * EPS
    gait = np.full(len(b), _STOP, dtype=np.int64)
    gait = np.where(is_g, np.where(inp["food_ok"], _STOP, _WALK), gait)
    gait = np.where(is_f, np.where(rs.startle_left > 0, _STOP, _RUN), gait)
    gait = np.where(is_h & ~crouch, np.where(seen, _RUN, _WALK), gait)
    gait = (gait * has_dir).astype(np.int8)
    vel = normalize(raw) * cfg.herb_speed
    vel = vel * sp["speed"][gait][:, None]
    eat = np.where(is_g, sp["eat"][gait], 0.0)
    rest = (b == SLEEP) & np.asarray(inp["in_cover"], dtype=bool)
    drain = sp["drain_mult"][gait] * np.where(rest, 1.0 - p["sleep_rest"] * float(inp["dark"]), 1.0)
    see = np.where(is_g, p["graze_head_down"], np.where(b == SLEEP, p["sleep_sight"], 1.0))
    still = (b == FREEZE) | (b == SLEEP) | crouch
    face = np.where(((b == FREEZE) & (away != 0.0).any(1))[:, None], -away, 0.0)
    return dict(vel=vel, gait=gait, eat=eat, drain=drain, see=see, still=still, crouch=crouch, face=face)


def tick(rs: RepState) -> None:
    """스텝 끝 (모듈 docstring D)."""
    rs.steps_in = rs.steps_in + 1
    rs.lock_left = rs.lock_left - 1
    rs.startle_left = np.maximum(rs.startle_left - 1, 0)
    rs.wake_left = np.maximum(rs.wake_left - 1, 0)


def perceive(rs: RepState, p: dict, g: dict, idx=None) -> None:
    """관측 뒤 away·recency 갱신 (모듈 docstring E). `idx` 가 있으면 그 행만(리스폰 관측)."""
    sl = slice(None) if idx is None else idx
    seen = np.asarray(g["pred_count"])[sl] > 0
    r = rs.recency[sl] * p["recency_decay"]
    r[seen] = 1.0
    rs.recency[sl] = r
    aw = rs.away[sl]
    aw[seen] = np.asarray(g["away_from_pred"])[sl][seen]
    rs.away[sl] = aw


def obs_extra(rs: RepState, p: dict, g: dict, idx=None) -> np.ndarray:
    """추가 관측 9칸 (n, 9) float32, 순서 `OBS_EXTRA_NAMES`: pred_approach(가장 가까운 보이는 위협의 접근 속력 [0,1], 없으면
    0.5), kin_alarm(보이는 동족 중 FLEE 비율, 동족이 없으면 0), 현재 행동 one-hot 5, min(steps_in/steps_norm, 1),
    threat_recency. steps_in 은 tick 뒤 값이라 같은 스텝의 훅 `World.beh_steps` 보다 1 크다(모듈 docstring 파리티 메모)."""
    sl = slice(None) if idx is None else idx
    b = rs.behavior[sl]
    n = len(b)
    o = np.zeros((n, len(OBS_EXTRA_NAMES)), dtype=np.float32)
    o[:, 0] = np.asarray(g["pred_approach"])[sl]
    o[:, 1] = np.asarray(g["kin_alarm"])[sl]
    o[np.arange(n), 2 + b.astype(np.int64)] = 1.0
    o[:, 7] = np.minimum(rs.steps_in[sl] / p["steps_norm"], 1.0)
    o[:, 8] = rs.recency[sl]
    return o
