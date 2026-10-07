"""V2 학습 환경 World — v1 `env/world.py` 에서 출발한 사본.

v1 파일은 언리얼에 연결된 계약(관측 7·행동 4)의 원본이라 한 줄도 바꾸지 않는다
(`Docs/RL_Policy/RL_V2_PLAN.md` 결정 3). V2 기능(속도·경계·기억·대담함·환경 상호작용)은
이 사본에 **스위치로** 붙인다. 스위치를 모두 끈 이 World 는 같은 시드에서 v1 World 와
결과가 완전히 같아야 한다 — `tests/test_env_v2.py` 가 고정한다.

기능 스위치는 버전 설정(`configs/v2*.yaml`)의 `features:` 블록이다(`env_v2/features.py`). 새 기능이 뽑는
난수는 기능마다 따로 둔 스트림 `self.feature_rng(name)` 에서만 뽑는다. v1 난수 호출 순서가 바뀌면
같은 시드의 세계가 조용히 달라지고, 기능끼리 스트림을 나눠 쓰면 기능 하나를 켜고 끌 때 다른 기능의
세계가 바뀌기 때문이다 (계획서 4.4, 4.8).

구현한 기능 (꺼진 기능의 코드 경로는 v1 과 같다):
- food_v (v2.0b, 계획서 4.9.1): 셀마다 식생 용량 V. 섭식이 V 를 깎고 재생은 cap0 대신 V 를 향한다.
  V 는 반감기 h 로 cap0 에 천천히 돌아온다. 스텝 순서는 `_food_v_step`, 통계는 `food_stats`·`food_cells`.
- speed (v2.1, 계획서 4.3·4.4·4.5): 행동이 5개가 된다(idx 4 = speed). 문턱으로 정지·걷기·뛰기를 정하고,
  상태가 v1 조향 속도의 크기, 섭식 배수, 대사를 정한다. 에너지 보상은 계수 하나로 순변화(#4)로 바꾼다.
  난수를 쓰지 않는다. 스텝 순서는 `_gait_step`, 통계는 `gait_stats`(v1 `stats()` 10열 밖).
- vigilance (v2.2, 계획서 4.2·4.3·4.4, #1·#5): 관측 하나(threat_recency)와 행동 하나(vigilance)가 붙는다.
  a_vig > 문턱이면 경계: 속력 0(speed 보다 우선), 섭식 배수 eat_mult(4.4 표 0), 대사는 정지 대사, 다음 관측의
  시야각 fov_deg(360°, 반경 see_r 그대로), heading 은 위협 쪽(ThreatDir). threat_recency·ThreatDir 는 개체별이고
  리스폰 때 초기화한다. 난수를 쓰지 않는다. 정의와 스텝 순서는 `_vigil_step`·`_perceive`, 통계는 `vigil_stats`.
  계수 threat_flee(10-03, 1-5 Gate E2b 보고용 #18 변형)는 0 이면 꺼져 있다(`_threat_flee_term`).
- vigil_window (v2.2r, 10-03 R2·수정 제안서 3.1 (나)): vigilance 위에 얹는 경계 재설계 스위치. '창' = 결정 때 포식자
  안 보임 & threat_recency > theta. action false 면 경계 행동 열을 빼고(관측 8 은 그대로, T1·L), window_only 면 경계가
  창 안에서만 효력이 있고(W′), look_back 이면 '정지 중이고 창 안이면 heading ← ThreatDir' 반사를 둔다(L). 난수를
  쓰지 않는다. 정의는 `_window_params`·`_look_back`, 통계는 `window_stats`. 끄면 v2.2 그대로다.
- daynight (v2.4, 계획서 4.9.2·4.2·#21): 세계마다 하루 길이 T 와 시작 위상 o 를 reset 때 자기 스트림에서 뽑고, 어둠 d
  (낮 0, 밤 1, 전환 앞뒤 박명은 선형)가 초식의 포식자 탐지 반경·섭식·정지 비경계 개체의 휴식 대사를 줄인다. 관측
  visibility·to_transition 두 칸이 붙는다. 동족 시야·관측 2 의 분모·포식자는 그대로다. speed 를 함께 켜야 한다.
  정의는 `_daynight_params`·`_daynight_update`, 통계는 `daynight_stats`. 낮 고정 세계(d = 0)는 v2.1 동역학 그대로다.
- pred_sleep (v2.4s, 10-07 사용자 결정 A안): daynight 위에 얹는다. 세계마다 야행성 비율 q 를 뽑고 포식자마다 확률 q 로
  야행성을 정한다(자기 스트림). 주행성 포식자는 어둠 d ≥ sleep_dark 면 잔다 — 멈추고 사냥하지 않고 초식 시야에 보이지
  않는다(굴에 있다). 깨어 있는 주행성 포식자는 twilight_slow 면 속력이 (1 − d) 배다. 야행성은 v2.4 그대로 움직인다.
  정의는 `_pred_sleep_params`·`_daynight_update`, 통계는 `pred_sleep_stats`.
- repertoire (v3 R0, 명세 `Docs/RL_Policy/RL_V3_R0_SPEC.md` 2·3절): speed·daynight 위에 얹는다(vigilance 와는 함께 켜지 않는다).
  행동이 한 열 'behavior'(정수 행동 번호. 정수가 아니면 거부)가 되고, v1 조향·보행 대신 행동 실행기(`env_v2/repertoire.py`:
  잠금·사건·결정 지연, 행동별 제어기)가 속도·보행·섭식·지각을 정한다. 장치: M1 정지 탐지(FREEZE·도착 HIDE·SLEEP 의 표적 선택
  체감 거리 × c_still), M2 놀람 정지, M4 잠 진입·기상, M5 GRAZE 고개 숙임(자기 탐지 반경), M6 행동별 은신 배수(은신처 안의
  웅크린 HIDE·GRAZE·SLEEP·그 밖, 계수 넷), SLEEP 시야 배수, SLEEP 전용 은신처 휴식 할인(daynight.rest_night 대신). 개체 행동
  상태(애니메이션 계약)는 스텝 뒤 훅 `World.behavior`·`beh_phase`·`beh_steps`·`beh_seq` 다. 난수를 쓰지 않는다(사건 결정
  지연은 세계 시드·슬롯·세대의 해시다). 추가 관측 9칸은 `rep_obs_extra` 가 늘 계산하고 obs_extra 가 true 일 때만 관측에
  붙는다. 통계는 `repertoire_stats`(슬롯별 전환·깜빡임 수는 `rep_slot_counts`). daynight_stats 의 휴식·먹기 열은 이 세계에서
  행동 기준이다(휴식 = 은신처 안 SLEEP, 먹기 = 먹이 셀의 GRAZE). v3 R1 은 결정 미리 보기 `rep_peek`(다음 스텝의 arbitrate 가
  요청을 읽는 개체, 순수 함수 — 학습·판정 마스크용, `env_v2/rep_policy.py`)를 더한다. 동역학은 바뀌지 않는다.
- threats (v3 R0, 명세 3절 M3·플레이어형 위협): daynight 위에 얹는다. reset 마다 잠행형 비율 p_stalk 를 뽑아 포식자마다
  잠행-돌진형을 정하고(잠행형은 근접형이다), 세계의 player_frac 에 플레이어형 위협 하나를 포식자 칸 끝에 더한다(밤에 자지
  않고 배회·잠행·돌진·휴식 모드를 바꾼다. 초식에게는 포식자와 같은 관측 칸으로 보인다). 자기 스트림 part 0(잠행형)·1(플레이어
  배치)·2(플레이어 모드)·3(플레이어 배회 선회)만 쓴다. 통계는 `threats_stats`.
  repertoire·threats 중 하나라도 켜면 포식자 스텝은 `_step_predators_v3` 다(v1 스트림 호출은 v2.4s 와 같은 모양).

행동·관측 수는 설정에서 읽는다: `action_names(cfg)`·`action_dim(cfg)`·`obs_names(cfg)`·`obs_dim(cfg)`, 세계마다
`World.act_names`·`World.act_dim`·`World.obs_names`·`World.obs_dim`. v1 4개(7개) 뒤에 켠 기능의 칸이 버전 순으로
붙는다(앞 버전을 건너뛰면 뒤 칸이 당겨진다, 계획서 4.1). 모듈 상수 `ACT_DIM`(4)·`OBS_DIM`(7)은 v1 수다.
"""

from __future__ import annotations

import math

import numpy as np

from . import repertoire as rep
from .features import Features, _check_name, _check_part, feature_stream, features_of
from .steering import EPS, clamp_magnitude, normalize, steer

# 관측 열 인덱스 (§3.1). 이 순서가 언리얼 FEcoObservationFragment와 일치해야 한다.
OBS_FOOD_DENSITY = 0
OBS_PREDATOR_COUNT = 1
OBS_PREDATOR_DISTANCE = 2
OBS_KIN_COUNT = 3
OBS_ENERGY = 4
OBS_RECENT_PREDATION = 5
OBS_COVER_DISTANCE = 6
OBS_DIM = 7  # v1 관측 수 — 세계의 실제 관측 수는 World.obs_dim
OBS_NAMES_V1 = ("food_density", "pred_count", "pred_dist", "kin_count", "energy", "recent_predation", "cover_dist")
OBS_THREAT_RECENCY = 7  # vigilance 를 켠 세계의 threat_recency 열 (계획서 4.2 idx 7, 관측 첫 추가 칸)

ACT_DIM = 4  # forage, cohesion, flee_dist, cover (§3.2). v1 행동 수 — 세계의 실제 행동 수는 World.act_dim
ACT_NAMES_V1 = ("forage", "cohesion", "flee_dist", "cover")
ACT_SPEED = 4  # speed 를 켠 세계의 보행 행동 열 (계획서 4.3 idx 4)
# vigilance 행동 열은 speed 가 켜져 있으면 5(계획서 4.3), 아니면 4 다. 세계마다 World.act_names.index("vigilance")

# 보행 상태 번호 (계획서 4.4). replay_v2.GAIT_* 와 같다.
GAIT_STOP, GAIT_WALK, GAIT_RUN = 0, 1, 2

# food_stats 의 "하한에 붙은 셀": V/cap0 ≤ floor + 이 값. 휴식 회복이 훼손 뒤에 오므로 하한까지 깎인 셀도
# 스텝 끝에는 ρ·(1 − floor)만큼 위에 있다(반감기 300 에서 0.0021). 통계 정의이고 동역학 계수가 아니다.
FOOD_V_FLOOR_TOL = 0.01

# gait_stats 의 지표 정의 (계획서 6.2, 통계 정의이고 동역학 계수가 아니다).
# B1 거리 구간 [0, 0.25), [0.25, 0.5), [0.5, 1] (× see_r). "포식자 가까움" = 보임 & d_pred < B1_EDGES[1]·see_r
# (앞 두 구간, 계획서 6.2 의 d_pred < 0.5·see_r 이고 Gate E1 구간과 같다).
B1_EDGES = (0.25, 0.5)
# B2·hungry_frac 의 "배고픔" = 결정 때(스텝 전) energy < HUNGRY·max_energy (v1 react_hunger 와 같은 문턱).
HUNGRY = 0.5
# gait_stats 누적 히스토그램 모양: [실제 보행, 명령 보행, 포식자 거리 구간(안 보임 + B1 3구간), 배부름].
# 세계의 누적 배열은 앞에 경계 축 [비경계, 경계]가 붙은 (2,) + GAIT_HIST_SHAPE 다(vigilance 를 끄면 경계 칸은 0).
GAIT_HIST_SHAPE = (3, 3, 1 + len(B1_EDGES) + 1, 2)
# gait_stats() 열 순서. env_v2/rollout.py 가 speed 를 켠 세계의 행에 붙인다.
GAIT_STAT_COLUMNS = (
    "stop_frac", "walk_frac", "run_frac", "stall_frac",
    "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd",
    "hungry_frac", "starve_rate", "starve_share",
    "b1", "p_run_unseen", "p_run_d025", "p_run_d050", "p_run_d100",
    "b2", "p_stop_hungry", "p_stop_full",
    "b8", "b8_cmd", "intake_per_step", "drain_per_step",
)

# vigil_stats 의 지표 정의 (계획서 6.2 B3·B4·B5·B5′, 통계 정의이고 동역학 계수가 아니다).
# "최근 위협" = 결정 때 포식자 안 보임 & threat_recency > RECENT_THREAT (Gate E2 구간의 θ. 0.5 = 놓친 뒤 반감기 안).
# Gate E2(10-03, results/v2/e2/PREREG.md)는 θ 를 0.5 로 고정하고 통과했다(gate_e2.THETA 와 같다).
RECENT_THREAT = 0.5
# B5′ 의 recent_predation 상·하위 구간 (스텝 분위수, diagnose_v2.react_conditions 의 '위험 높음/낮음'과 같은 20%)
EMA_SPLIT_Q = 0.2
# vigil_stats 누적 히스토그램 모양: [구간 4(평시, 최근 위협·안 보임, 포식자 1마리 보임, 2마리 이상 보임),
# 결정 관측의 시야(0 = 기본 FOV, 1 = 경계 시야 — 직전 스텝에 경계), 배부름, 경계]
VIG_HIST_SHAPE = (4, 2, 2, 2)
# 시야와 무관한 기준 구간의 히스토그램 모양: [기준 구간 3(평시, 최근 반경 안·지금 밖, 지금 반경 안), 경계].
# '반경 안' = 결정 때 위치에서 거리 ≤ see_r 인 포식자가 있다(FOV 무시). 흔적은 threat_recency 와 같은 decay 다
VIG_TRUTH_SHAPE = (3, 2)
# vigil_stats() 열 순서. env_v2/rollout.py 가 vigilance 를 켠 세계의 행에 붙인다. 앞 28열은 1-4 첫 구현의 순서
# 그대로이고(rollout·diagnose 는 이름으로 읽는다), 뒤 16열은 10-03 검토에서 더한 360° 치우침 분리 열이다.
VIGIL_STAT_COLUMNS = (
    "vig_frac", "seg_seen_frac", "seg_recent_frac", "seg_calm_frac",
    "p_vig_seen", "p_vig_recent", "p_vig_calm", "b3", "b3_narrow",
    "b4", "b4_n", "b4_vig", "b4_vig_n",
    "b5", "p_vig_hungry", "p_vig_full",
    "b5p_pred", "p_vig_pc0", "p_vig_pc1", "p_vig_pc2", "b5p_ema",
    "b8_vig", "obs_wide_frac", "kin_narrow", "kin_wide", "pred_narrow", "pred_wide", "threat_mean",
    "p_vig_seen_narrow", "p_vig_pc0_narrow", "p_vig_pc1_narrow", "p_vig_pc2_narrow", "b5p_pred_narrow",
    "b4_narrow", "b4_narrow_n", "b4_wide", "b4_wide_n",
    "seg_near_truth_frac", "seg_recent_truth_frac", "p_vig_near_truth", "p_vig_recent_truth", "p_vig_calm_truth",
    "b3_truth", "b5p_truth",
)

# window_stats 누적 히스토그램 모양 (v2.2r, 수정 제안서 3.8 B3 정의): [구간 3(평시, 창 안, 포식자 보임), 배부름, 실제 정지,
# 경계]. 구간·배부름은 결정 때 상태, 창은 동역학과 같은 theta 로 정한다(vigil_stats 의 RECENT_THREAT 와 별개).
# 실제 정지 = 이번 스텝의 실제 보행이 정지(경계 포함, speed 를 끈 세계는 경계)다.
WINDOW_HIST_SHAPE = (3, 2, 2, 2)
# window_stats() 열 순서. env_v2/rollout.py 가 vigil_window 를 켠 세계의 행에 붙인다.
WINDOW_STAT_COLUMNS = (
    "win_frac", "p_stop_win", "p_stop_calm", "p_stop_win_full", "p_stop_calm_full", "b3_l",
    "p_stop_win_hungry", "p_stop_calm_hungry",
    "p_vig_win", "p_vig_win_full", "p_vig_win_hungry", "p_vig_calm_w",
    "look_frac", "look_win_frac",
)

# daynight_stats 위상 구간 (계획서 6.1-6, 2-5 행): 낮 d ≤ 0.2, 박명 0.2 < d < 0.8, 밤 d ≥ 0.8. d 는 박명 폭 정수 스텝의
# 유리수라 문턱 비교에 DN_TOL 여유를 둔다(관측 visibility 로 구간을 나누는 도구는 `daynight_seg_edges`).
DN_EDGES = (0.2, 0.8)
DN_TOL = 1e-9
# pred_sleep_stats() 열 순서 (v2.4s). env_v2/rollout.py 가 pred_sleep 을 켠 세계의 행에 붙인다.
PSLEEP_STAT_COLUMNS = ("pred_noct_frac", "pred_noct_n", "pred_asleep_mean")
# start_induce 의 유도 에너지 범위(max_energy 비율). 배고픔 문턱 HUNGRY(0.5) 아래다
INDUCE_ENERGY = (0.2, 0.5)
# 개체-스텝 히스토그램 [위상 3, 배부름 2, 결정 때 은신처 안 2, 실제 보행 3, 경계 2, 먹이 셀 2]. 먹이 셀 = 이번 스텝의
# 섭식 위치(이동 뒤) 셀의 기준 용량 cap0 > 0 (N5′ '먹이 셀', 10-06 사전 등록)
DN_HIST_SHAPE = (3, 2, 2, 3, 2, 2)
# B1·B2 위상 구간판 [경계 2, 위상 3, 명령 보행 3, 포식자 거리 구간 4, 배부름 2] (gait_stats 와 같은 정의, 위상 축만 더함)
DN_B_SHAPE = (2, 3, 3, 1 + len(B1_EDGES) + 1, 2)
# daynight_stats() 열 순서. env_v2/rollout.py 가 daynight 를 켠 세계의 행에 붙인다.
DAYNIGHT_STAT_COLUMNS = (
    "dn_period", "dn_offset", "dn_day_fixed", "dn_induced", "dark_mean", "frac_day", "frac_twi", "frac_night",
    "pred_rate_day", "pred_rate_twi", "pred_rate_night",
    "starve_rate_day", "starve_rate_twi", "starve_rate_night",
    "intake_day", "intake_twi", "intake_night", "intake_ratio_nd", "drain_day", "drain_night",
    "p_rest_cover_day", "p_rest_cover_night", "n1",
    "p_eat_night_hungry", "p_eat_night_full", "n5p", "p_eat_day_hungry", "p_eat_day_full",
    "p_stop_day", "p_stop_night", "p_run_day", "p_run_night", "p_cover_day", "p_cover_night",
    "p_stop_night_hungry", "p_stop_night_full",
    "b1_day", "b1_night", "b2_day", "b2_night", "n2",
)


# repertoire_stats 의 깜빡임 창: 행동 A → B → A 가 이 초 안에 되돌아오면 깜빡임(초안 지표 '3초 안 A-B-A'). 통계 정의다
FLICKER_SECONDS = 3.0
# repertoire_stats() 열 순서 (v3 R0). env_v2/rollout.py 가 repertoire 를 켠 세계의 행에 붙인다. 행동 이름은 repertoire.BEHAVIOR_NAMES
_BN = rep.BEHAVIOR_NAMES
REP_STAT_COLUMNS = (
    tuple(f"use_{b}" for b in _BN) + tuple(f"use_day_{b}" for b in _BN) + tuple(f"use_night_{b}" for b in _BN)
    + tuple(f"use_seen_{b}" for b in _BN) + tuple(f"use_unseen_{b}" for b in _BN)
    + tuple(f"pred_rate_{b}" for b in _BN) + tuple(f"starve_rate_{b}" for b in _BN)
    + ("seen_frac", "switch_per_sec", "flicker_rate", "decide_frac")
)
# 포식자 유형 번호 (threats). 원거리형은 유형이 아니라 pred_ranged 다(추격형 중 원거리)
PT_CHASER, PT_STALKER, PT_PLAYER = 0, 1, 2
# 잠행형 상태: 배회·잠행(표적 체감 거리 > stalk_dist), 돌진, 탈진
ST_ROAM, ST_POUNCE, ST_EXHAUST = 0, 1, 2
# 플레이어 모드: 배회, 잠행 접근, 돌진, 휴식
PM_WANDER, PM_STALK, PM_CHARGE, PM_REST = 0, 1, 2, 3
# threats_stats() 열 순서 (v3 R0). 포획률은 개체-스텝당. catch_rate_chaser 는 근접 추격형, ranged 는 원거리 추격형
THREAT_STAT_COLUMNS = ("p_stalk", "stalker_n", "player_present", "catch_rate_chaser", "catch_rate_ranged",
                       "catch_rate_stalker", "catch_rate_player", "pounce_n", "pounce_hit", "player_charge_n")


WORLD_PARAM_KEYS = ("world_size", "predator_count", "pred_speed_mult", "ranged_frac", "cover_frac", "food_regen_mult")


def world_params(cfg, seed: int) -> dict:
    """세계 시드 하나가 정하는 무작위화 매개변수(`World.reset` 이 같은 순서로 뽑는 값)를 세계를 만들지 않고 낸다.

    reset 의 v1 스트림 `default_rng(seed)` 앞 여섯 번 뽑기와 같다: 크기, 포식자 수 M, 포식자 속도 배수, 원거리형 비율,
    은신처 비율 목표, 먹이 재생 배수. 학습 세계 균형 추출(`env_v2/vec_env.py`, S1-a 10-04 결정)과 진단이 쓴다.
    reset 의 뽑는 순서를 바꾸면 이 함수도 같이 바꿔야 한다(`tests/test_world_sampling_v2.py` 가 맞는지 본다).
    """
    rd = cfg.rand
    r = np.random.default_rng(int(seed))
    size = float(r.uniform(*rd["world_size"]))
    m = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
    psm = float(r.uniform(*rd["pred_speed_mult"]))
    rf = float(r.uniform(*rd["ranged_frac"]))
    cf = float(r.uniform(*rd["cover_frac"]))
    fr = float(r.uniform(*rd["food_regen_mult"]))
    return dict(zip(WORLD_PARAM_KEYS, (size, m, psm, rf, cf, fr)))


def action_names(cfg) -> tuple[str, ...]:
    """설정(또는 `Features`)의 세계가 받는 행동 이름. 순서 = 행동 열 번호 (계획서 4.3).

    v1 4개 뒤에 켠 기능의 행동이 버전 순으로 붙는다: speed(v2.1), vigilance(v2.2). 앞 기능을 끄면 뒤 칸이
    당겨진다(speed 없이 vigilance 만 켜면 vigilance 가 열 4). 한번 정한 순서는 바꾸지 않는다.
    vigil_window(v2.2r)를 켜고 action 이 false 면 vigilance 열이 없다(관측 threat_recency 는 그대로).
    repertoire(v3)를 켜면 행동은 한 열 'behavior'(정수 행동 번호를 float 로. env_v2/repertoire.py)뿐이다.
    """
    f = cfg if isinstance(cfg, Features) else features_of(cfg)
    if f.enabled("repertoire"):
        return ("behavior",)
    names = ACT_NAMES_V1
    if f.enabled("speed"):
        names = names + ("speed",)
    if f.enabled("vigilance") and (not f.enabled("vigil_window") or f.params("vigil_window")["action"]):
        names = names + ("vigilance",)
    return names


def action_dim(cfg) -> int:
    """설정의 세계가 받는 행동 수. v1·v2.0·v2.0b 4, speed 를 켜면 5, vigilance 까지 켜면 6(v2.2r action false 면 5)."""
    return len(action_names(cfg))


def obs_names(cfg) -> tuple[str, ...]:
    """설정(또는 `Features`)의 세계가 내는 관측 이름. 순서 = 관측 열 번호 (계획서 4.2).

    v1 7개(이름은 diagnose_v2.OBS_NAMES 와 같다) 뒤에 켠 기능의 관측이 붙는다: threat_recency(v2.2),
    visibility·to_transition(v2.4). 앞 기능을 끄면 뒤 칸이 당겨진다 — v2.1 위의 v2.4 는 visibility 가 idx 7,
    to_transition 이 idx 8 이다(계획서 4.2 의 9·10 은 v2.2·v2.3 을 모두 했을 때 번호이고, idx 7~10 은 V2a 에서 확정한다).
    도구는 칸을 번호가 아니라 이름으로 찾는다.
    repertoire(v3)의 obs_extra 가 true 면 뒤에 9칸(`repertoire.OBS_EXTRA_NAMES`)이 붙는다(R0 설정은 false).
    """
    f = cfg if isinstance(cfg, Features) else features_of(cfg)
    names = OBS_NAMES_V1
    if f.enabled("vigilance"):
        names = names + ("threat_recency",)
    if f.enabled("daynight"):
        names = names + ("visibility", "to_transition")
    if f.enabled("repertoire") and f.params("repertoire").get("obs_extra") is True:
        names = names + rep.OBS_EXTRA_NAMES
    return names


def obs_dim(cfg) -> int:
    """설정의 세계가 내는 관측 수. v1·v2.0·v2.0b·v2.1 7, vigilance 를 켜면 8, v2.1 + daynight 9."""
    return len(obs_names(cfg))


def _num(feature: str, key: str, x) -> float:
    """기능 계수 하나가 유한한 숫자인지 본다(bool 은 거부)."""
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) or not math.isfinite(x):
        raise ValueError(f"features.{feature}.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
    return float(x)


def _vigil_params(p: dict, base_fov_deg: float) -> dict:
    """vigilance 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    - threshold ∈ [0, 1]: a_vig > threshold 면 경계 (계획서 4.3 "0.5 를 넘으면", 같으면 경계가 아니다)
    - decay ∈ [0, 1]: threat_recency 의 스텝당 감쇠 계수. 반감기 = ln 0.5 / ln decay 스텝 (0 이면 '지금 보임'과 같다)
    - eat_mult ≥ 0: 경계 중 섭식 배수(`_eat` 의 want 에 곱한다)
    - fov_deg ∈ [fov_deg(v1), 360]: 경계한 스텝 뒤 관측의 시야각. 360 이면 각도 판정 없이 반경 see_r 안 전부다
      (cos(180°) = −1 과의 비교는 반올림으로 정반대 방향을 놓칠 수 있어 −inf 로 둔다)
    - threat_flee ≥ 0: 10절 #18 조향 변형 항의 배수(`_threat_flee_term`). 0 이면 항이 없다(1-4 구현과 비트 단위로
      같다 — `steer` 에 아무것도 더하지 않는다). Gate E2b 의 '계속 뛰기 + 위협 반대 항' 보고 팔만 1 로 둔다
    """
    th = _num("vigilance", "threshold", p["threshold"])
    dec = _num("vigilance", "decay", p["decay"])
    eat = _num("vigilance", "eat_mult", p["eat_mult"])
    fov = _num("vigilance", "fov_deg", p["fov_deg"])
    tf = _num("vigilance", "threat_flee", p["threat_flee"])
    if not 0.0 <= th <= 1.0:
        raise ValueError(f"features.vigilance.threshold 는 [0, 1] 이어야 한다(행동은 sigmoid 뒤 값). 받은 값: {th}")
    if not 0.0 <= dec <= 1.0:
        raise ValueError(f"features.vigilance.decay 는 [0, 1] 이어야 한다. 받은 값: {dec}")
    if eat < 0.0:
        raise ValueError(f"features.vigilance.eat_mult 는 0 이상이어야 한다. 받은 값: {eat}")
    if not float(base_fov_deg) <= fov <= 360.0:
        raise ValueError(f"features.vigilance.fov_deg 는 기본 시야각 {base_fov_deg} 이상 360 이하여야 한다. 받은 값: {fov}")
    if tf < 0.0:
        raise ValueError(f"features.vigilance.threat_flee 는 0 이상이어야 한다. 받은 값: {tf}")
    wide_cos = -math.inf if fov >= 360.0 else math.cos(math.radians(fov) * 0.5)
    half_life = math.log(0.5) / math.log(dec) if 0.0 < dec < 1.0 else (0.0 if dec == 0.0 else math.inf)
    return dict(threshold=th, decay=dec, eat_mult=eat, fov_deg=fov, threat_flee=tf, wide_cos=wide_cos,
                half_life=half_life)


def _window_params(p: dict, f: Features) -> dict:
    """vigil_window 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (v2.2r, 수정 제안서 3.1 (나)).

    - action (bool): 경계 행동 열이 있나. false 면 행동에서 vigilance 열을 빼고(`action_names`) 경계는 일어나지 않는다.
      관측 threat_recency·ThreatDir 갱신(`_perceive`)은 vigilance 그대로다 — T1(관측 8만)·L(반사)
    - window_only (bool): 경계가 창 안 개체에서만 효력이 있다(W′). 창 밖에서 a_vig > threshold 여도 경계가 아니고
      speed 가 보행을 정한다. action 이 true 여야 한다
    - look_back (bool): 반사 돌아보기(L). 이번 스텝의 실제 보행이 정지이고 창 안이면 heading ← ThreatDir(`_look_back`).
      정지를 speed 가 정하므로 speed 를 켜야 한다
    - theta ∈ [0, 1): 창 문턱. 창 = 결정 때 포식자 안 보임(관측 1 = 0) & threat_recency > theta. Gate E2 의 θ 0.5
      (RECENT_THREAT, 놓친 뒤 13스텝)를 적는다
    vigilance 를 켜야 한다(threat_recency·ThreatDir·경계 계수가 거기 있다).
    """
    if not f.enabled("vigilance"):
        raise ValueError("features.vigil_window 는 vigilance 를 함께 켜야 한다(threat_recency·ThreatDir 가 vigilance 에 있다)")
    out = {}
    for key in ("action", "window_only", "look_back"):
        if not isinstance(p[key], bool):
            raise ValueError(f"features.vigil_window.{key} 는 true/false 여야 한다. 받은 값: {p[key]!r}")
        out[key] = p[key]
    th = _num("vigil_window", "theta", p["theta"])
    if not 0.0 <= th < 1.0:
        raise ValueError(f"features.vigil_window.theta 는 [0, 1) 이어야 한다(threat_recency 는 보이면 1). 받은 값: {th}")
    out["theta"] = th
    if out["window_only"] and not out["action"]:
        raise ValueError("features.vigil_window.window_only 는 action: true 일 때만 쓴다(경계 행동 열이 없으면 효력도 없다)")
    if out["look_back"] and not f.enabled("speed"):
        raise ValueError("features.vigil_window.look_back 은 speed 를 함께 켜야 한다(반사 조건 '정지'를 speed 가 정한다)")
    return out


def _speed_params(p: dict) -> dict:
    """speed 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사하고 상태별 표를 만든다. 기본값은 없다.

    - thresholds [t_walk, t_run]: 0 ≤ t_walk ≤ t_run ≤ 1. a < t_walk 정지, a < t_run 걷기, 그 밖은 뛰기
    - gait_speed [0, s_walk, s_run] (× herb_speed): 정지는 0, 0 < s_walk ≤ s_run
    - gait_eat [e_stop, e_walk, e_run] ≥ 0: `_eat` 의 want 에 곱하는 섭식 배수
    - c_rest, c_move ≥ 0: drain_mult[g] = c_rest + c_move·gait_speed[g]² (스텝 대사 = energy_drain × drain_mult)
    - net_energy_reward: true 면 에너지 보상이 순변화 e_new − e_prev, false 면 v1 획득량 (#4)
    """
    def num(key, x):
        if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) \
                or not math.isfinite(x):
            raise ValueError(f"features.speed.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
        return float(x)

    def vec(key, n):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != n:
            raise ValueError(f"features.speed.{key} 는 값 {n}개 목록이어야 한다. 받은 값: {x!r}")
        return tuple(num(key, v) for v in x)

    t_walk, t_run = vec("thresholds", 2)
    speed = vec("gait_speed", 3)
    eat = vec("gait_eat", 3)
    c_rest, c_move = num("c_rest", p["c_rest"]), num("c_move", p["c_move"])
    net = p["net_energy_reward"]
    if not 0.0 <= t_walk <= t_run <= 1.0:
        raise ValueError(f"features.speed.thresholds 는 0 ≤ 걷기 ≤ 뛰기 ≤ 1 이어야 한다. 받은 값: {[t_walk, t_run]}")
    if speed[0] != 0.0 or not 0.0 < speed[1] <= speed[2]:
        raise ValueError(f"features.speed.gait_speed 는 [0, 걷기, 뛰기], 0 < 걷기 ≤ 뛰기 여야 한다(정지는 속력 0). "
                         f"받은 값: {list(speed)}")
    if min(eat) < 0.0:
        raise ValueError(f"features.speed.gait_eat 는 0 이상이어야 한다. 받은 값: {list(eat)}")
    if c_rest < 0.0 or c_move < 0.0:
        raise ValueError(f"features.speed.c_rest·c_move 는 0 이상이어야 한다. 받은 값: {c_rest}, {c_move}")
    if not isinstance(net, bool):
        raise ValueError(f"features.speed.net_energy_reward 는 true/false 여야 한다. 받은 값: {net!r}")
    sp = np.asarray(speed, dtype=np.float64)
    return dict(thresholds=(t_walk, t_run), speed=sp, eat=np.asarray(eat, dtype=np.float64),
                c_rest=c_rest, c_move=c_move, drain_mult=c_rest + c_move * sp * sp, net_energy_reward=net)


def _food_v_params(p: dict) -> dict:
    """food_v 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    alpha ≥ 0, 0 ≤ floor ≤ 1, 반감기는 하나 이상의 양수(스텝), floor ≤ init_frac[0] ≤ init_frac[1] ≤ 1.
    alpha = 0 이면 훼손이 없어 V 가 cap0 로 돌아가기만 한다.
    """
    def num(key, x):
        if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) \
                or not math.isfinite(x):
            raise ValueError(f"features.food_v.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
        return float(x)

    alpha, floor = num("alpha", p["alpha"]), num("floor", p["floor"])
    hl, fr = p["recovery_half_lives"], p["init_frac"]
    if not isinstance(hl, (list, tuple)) or not hl:
        raise ValueError(f"features.food_v.recovery_half_lives 는 반감기(스텝) 목록이어야 한다. 받은 값: {hl!r}")
    if not isinstance(fr, (list, tuple)) or len(fr) != 2:
        raise ValueError(f"features.food_v.init_frac 는 [하, 상] 두 값이어야 한다. 받은 값: {fr!r}")
    half_lives = tuple(num("recovery_half_lives", h) for h in hl)
    lo, hi = (num("init_frac", x) for x in fr)
    if alpha < 0.0:
        raise ValueError(f"features.food_v.alpha 는 0 이상이어야 한다. 받은 값: {alpha}")
    if not 0.0 <= floor <= 1.0:
        raise ValueError(f"features.food_v.floor 는 [0, 1] 의 cap0 비율이어야 한다. 받은 값: {floor}")
    if min(half_lives) <= 0.0:
        raise ValueError(f"features.food_v.recovery_half_lives 는 양수여야 한다. 받은 값: {list(half_lives)}")
    if not floor <= lo <= hi <= 1.0:
        raise ValueError(f"features.food_v.init_frac 는 floor({floor}) ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    return dict(alpha=alpha, floor=floor, half_lives=half_lives, init_frac=(lo, hi))


def _daynight_params(p: dict, f: Features) -> dict:
    """daynight 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    - periods: 하루 길이 T(스텝) 목록, 하나 이상의 양의 짝수 정수(낮·밤이 T/2 씩, 계획서 4.9.2 {600, 900, 1800})
    - twilight ∈ (0, 0.25]: 전환 앞뒤 박명 폭(T 비율). twilight·T 는 정수 스텝이어야 한다(구간 문턱이 비트 단위로 같게)
    - detect_night·eat_night·rest_night ∈ [0, 1]: 어둠 d 에서 (1 − x·d) 를 곱한다. 0 이면 그 효과가 없다
    - fixed_day_frac ∈ [0, 1]: reset 마다 이 확률로 낮 고정 세계(d = 0, 관측은 중립값 1·1)
    - transition_norm ≥ max(periods)/2: to_transition = 남은 스텝 / transition_norm (계약 900, 계획서 4.2)
    - start_induce ∈ [0, 1]: 시작 상태 유도 비율(0 = 끔). `_daynight_reset`·`_respawn` docstring
    - rest_cover_only (bool): true 면 휴식 할인을 결정 때 은신처 안에서 멈춘 개체만 받는다(v2.4b). false = v2.4
    speed 를 함께 켜야 한다(휴식 대사는 보행 상태의 정지 대사에 곱하고, 통계가 보행을 센다).
    """
    if not f.enabled("speed"):
        raise ValueError("features.daynight 는 speed 를 함께 켜야 한다(v2.4 는 v2.1 위의 버전이다)")
    per = p["periods"]
    if not isinstance(per, (list, tuple)) or not per:
        raise ValueError(f"features.daynight.periods 는 하루 길이(스텝) 목록이어야 한다. 받은 값: {per!r}")
    periods = []
    for x in per:
        if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x <= 0 or x % 2:
            raise ValueError(f"features.daynight.periods 는 양의 짝수 정수여야 한다. 받은 값: {list(per)}")
        periods.append(int(x))
    tw = _num("daynight", "twilight", p["twilight"])
    if not 0.0 < tw <= 0.25:
        raise ValueError(f"features.daynight.twilight 는 (0, 0.25] 의 T 비율이어야 한다. 받은 값: {tw}")
    tw_steps = []
    for T in periods:
        k = tw * T
        if abs(k - round(k)) > 1e-9 or round(k) < 1:
            raise ValueError(f"features.daynight.twilight·T 는 1 이상의 정수 스텝이어야 한다. T={T}: {k}")
        tw_steps.append(int(round(k)))
    mult = {}
    for key in ("detect_night", "eat_night", "rest_night", "fixed_day_frac", "start_induce"):
        x = _num("daynight", key, p[key])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.daynight.{key} 는 [0, 1] 이어야 한다. 받은 값: {x}")
        mult[key] = x
    rco = p["rest_cover_only"]
    if not isinstance(rco, bool):
        raise ValueError(f"features.daynight.rest_cover_only 는 true/false 여야 한다. 받은 값: {rco!r}")
    norm = _num("daynight", "transition_norm", p["transition_norm"])
    if norm < max(periods) / 2:
        raise ValueError(f"features.daynight.transition_norm 은 가장 긴 상 길이 {max(periods) // 2} 이상이어야 한다. "
                         f"받은 값: {norm}")
    return dict(periods=tuple(periods), tw_steps=tuple(tw_steps), transition_norm=norm, rest_cover_only=rco, **mult)


def _pred_sleep_params(p: dict, f: Features) -> dict:
    """pred_sleep 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다.

    - nocturnal_frac = [하, 상], 0 ≤ 하 ≤ 상 ≤ 1: reset 마다 야행성 비율 q ~ U[하, 상]
    - sleep_dark ∈ (0, 1]: 주행성 포식자가 자는 어둠 문턱(d ≥ sleep_dark)
    - twilight_slow (bool): 깨어 있는 주행성 포식자 속력 × (1 − d)
    daynight 를 함께 켜야 한다(어둠 d 가 거기 있다).
    """
    if not f.enabled("daynight"):
        raise ValueError("features.pred_sleep 은 daynight 를 함께 켜야 한다(어둠 d 가 daynight 에 있다)")
    fr = p["nocturnal_frac"]
    if not isinstance(fr, (list, tuple)) or len(fr) != 2:
        raise ValueError(f"features.pred_sleep.nocturnal_frac 는 [하, 상] 두 값이어야 한다. 받은 값: {fr!r}")
    lo, hi = (_num("pred_sleep", "nocturnal_frac", x) for x in fr)
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"features.pred_sleep.nocturnal_frac 는 0 ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    sd = _num("pred_sleep", "sleep_dark", p["sleep_dark"])
    if not 0.0 < sd <= 1.0:
        raise ValueError(f"features.pred_sleep.sleep_dark 는 (0, 1] 이어야 한다. 받은 값: {sd}")
    ts = p["twilight_slow"]
    if not isinstance(ts, bool):
        raise ValueError(f"features.pred_sleep.twilight_slow 는 true/false 여야 한다. 받은 값: {ts!r}")
    return dict(nocturnal_frac=(lo, hi), sleep_dark=sd, twilight_slow=ts)


def _threats_params(p: dict, f: Features) -> dict:
    """threats 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (v3 R0, 명세 3절 M3·플레이어형 위협).

    - stalk_frac = [하, 상], 0 ≤ 하 ≤ 상 ≤ 1: reset 마다 p_stalk ~ U[하, 상], 포식자마다 확률 p_stalk 로 잠행-돌진형
    - stalk_dist > 0: 잠행형이 돌진을 시작하는 표적 체감 거리(M1·은신 배수가 든 거리)
    - stalk_speed·pounce_speed·exhaust_speed ≥ 0 (× herb_speed), pounce_steps ≥ 1, exhaust_steps ≥ 0 (정수 스텝)
    - player_frac ∈ [0, 1]: 플레이어형 위협이 있는 세계 비율
    - player_speeds = [배회, 잠행, 돌진] ≥ 0 (× herb_speed), player_mode_steps = [하, 상] 정수 1 ≤ 하 ≤ 상
    - player_stalk_p ∈ [0, 1], player_charge_dist > 0, player_charge_steps ≥ 1, player_rest_steps ≥ 0 (정수)
    - player_catch_r > 0, player_cooldown ≥ 0 (정수 스텝)
    daynight 를 함께 켜야 한다(v3 는 v2.4s 위의 버전이고, 플레이어는 낮밤과 무관하게 움직이는 위협이다).
    """
    if not f.enabled("daynight"):
        raise ValueError("features.threats 는 daynight 를 함께 켜야 한다(v3 는 v2.4s 위의 버전이다)")

    def integer(key, x, lo):
        if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x < lo:
            raise ValueError(f"features.threats.{key} 는 {lo} 이상의 정수(스텝)여야 한다. 받은 값: {x!r}")
        return int(x)

    def pair(key, n):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != n:
            raise ValueError(f"features.threats.{key} 는 값 {n}개 목록이어야 한다. 받은 값: {x!r}")
        return x

    lo, hi = (_num("threats", "stalk_frac", x) for x in pair("stalk_frac", 2))
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"features.threats.stalk_frac 는 0 ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    out = dict(stalk_frac=(lo, hi))
    for key in ("stalk_speed", "pounce_speed", "exhaust_speed"):
        x = _num("threats", key, p[key])
        if x < 0.0:
            raise ValueError(f"features.threats.{key} 는 0 이상이어야 한다. 받은 값: {x}")
        out[key] = x
    for key in ("stalk_dist", "player_charge_dist", "player_catch_r"):
        x = _num("threats", key, p[key])
        if x <= 0.0:
            raise ValueError(f"features.threats.{key} 는 양수여야 한다. 받은 값: {x}")
        out[key] = x
    for key in ("player_frac", "player_stalk_p"):
        x = _num("threats", key, p[key])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.threats.{key} 는 [0, 1] 이어야 한다. 받은 값: {x}")
        out[key] = x
    out["pounce_steps"] = integer("pounce_steps", p["pounce_steps"], 1)
    out["exhaust_steps"] = integer("exhaust_steps", p["exhaust_steps"], 0)
    out["player_charge_steps"] = integer("player_charge_steps", p["player_charge_steps"], 1)
    out["player_rest_steps"] = integer("player_rest_steps", p["player_rest_steps"], 0)
    out["player_cooldown"] = integer("player_cooldown", p["player_cooldown"], 0)
    sp = tuple(_num("threats", "player_speeds", x) for x in pair("player_speeds", 3))
    if min(sp) < 0.0:
        raise ValueError(f"features.threats.player_speeds 는 0 이상이어야 한다. 받은 값: {list(sp)}")
    out["player_speeds"] = sp
    ms = tuple(integer("player_mode_steps", x, 1) for x in pair("player_mode_steps", 2))
    if ms[0] > ms[1]:
        raise ValueError(f"features.threats.player_mode_steps 는 [하, 상], 하 ≤ 상 이어야 한다. 받은 값: {list(ms)}")
    out["player_mode_steps"] = ms
    return out


def daynight_phase(t: int, period: int, offset: int, tw_steps: int) -> tuple[float, int]:
    """스텝 t 의 (어둠 d, 다음 전환까지 남은 스텝 r) (계획서 4.9.2). 낮 고정 세계는 부르지 않는다(d = 0).

    s = (t + o) mod T, 낮 = s < T/2. e = s mod (T/2) 는 지난 전환 뒤 스텝, r = T/2 − e ∈ [1, T/2] 는 다음 전환까지.
    k = min(e, r), τ = 박명 폭(정수 스텝). 낮이면 d = clip(0.5 − k/(2τ), 0, 1), 밤이면 clip(0.5 + k/(2τ), 0, 1) —
    전환 순간 0.5, 전환 앞뒤 τ 스텝(계 0.1·T)에 걸쳐 0 과 1 을 선형으로 잇는다.
    C++ 꼴: e = Now − PhaseStart, r = PhaseEnd − Now (스텝), bNight = Phase == Night.
    """
    h = period // 2
    s = (int(t) + int(offset)) % period
    e = s % h
    r = h - e
    k = min(e, r)
    x = k / (2.0 * tw_steps)
    d = min(0.5 + x, 1.0) if s >= h else max(0.5 - x, 0.0)
    return d, r


def daynight_draws(dn: dict, seed: int, n_agents: int) -> dict:
    """세계 시드 하나가 정하는 낮밤 값(`World._daynight_reset` 이 같은 순서로 뽑는 값)을 세계를 만들지 않고 낸다.

    daynight 스트림 part 0 에서 정확히 3개: u0 → 낮 고정(u0 < fixed_day_frac), u1 → T = periods[⌊u1·n⌋],
    u2 → o = ⌊u2·T⌋. start_induce > 0 이면 part 2 에서 u → 유도(u < start_induce, 낮 고정이 아닐 때만)와 개체
    에너지 n_agents 개(U[0.2, 0.5], 늘 뽑는다). 유도면 o = T/2 − ⌈0.1·T⌉ (해 지기 0.1·T 스텝 전에 시작한다).
    """
    g = feature_stream(int(seed), "daynight", 0)
    u0, u1, u2 = g.random(3)
    per = dn["periods"]
    i = min(int(u1 * len(per)), len(per) - 1)
    T = per[i]
    out = dict(day_fixed=bool(u0 < dn["fixed_day_frac"]), period=T, offset=min(int(u2 * T), T - 1),
               tw_steps=dn["tw_steps"][i], induced=False, energy=None)
    if dn["start_induce"] > 0.0:
        g2 = feature_stream(int(seed), "daynight", 2)
        ui = float(g2.random())
        energy = g2.uniform(INDUCE_ENERGY[0], INDUCE_ENERGY[1], n_agents)
        if ui < dn["start_induce"] and not out["day_fixed"]:
            out.update(induced=True, energy=energy, offset=T // 2 - int(math.ceil(0.1 * T)))
    return out


def daynight_seg_edges(detect_night: float, tol: float = 1e-5) -> tuple[float, float]:
    """관측 visibility(float32)로 위상 구간을 나누는 문턱 (밤 | 박명 | 낮). `np.digitize(vis, edges)` 가 0 밤, 1 박명,
    2 낮을 낸다: 밤 = vis ≤ 1 − 0.8·detect_night, 낮 = vis ≥ 1 − 0.2·detect_night (d 구간과 같다). d 의 이웃 값 사이
    간격(≥ detect_night/(2τ))보다 훨씬 작은 tol 로 float32 반올림을 흡수한다. detect_night = 0 이면 나눌 수 없다.
    """
    if detect_night <= 0.0:
        raise ValueError("detect_night = 0 이면 visibility 가 늘 1 이라 위상 구간을 관측으로 나눌 수 없다")
    return (1.0 - DN_EDGES[1] * detect_night + tol, 1.0 - DN_EDGES[0] * detect_night - tol)


class World:
    """N=128 슬롯 고정, 죽으면 그 슬롯에 리스폰 (§4.3).

    `step()` 은 항상 [0,1] 행동을 받는다 (§1.3). (-3,3) 출력의 sigmoid 변환은
    VecEnv 래퍼(§6.2)의 책임이지 이 클래스의 책임이 아니다.
    """

    def __init__(self, cfg, seeds=None, meta_seed: int = 0):
        self.cfg = cfg
        if seeds is None:
            lo, hi = cfg.train_seeds
            seeds = range(lo, hi)
        self.seeds = np.asarray(list(seeds), dtype=np.int64)
        self.meta = np.random.default_rng(meta_seed)
        self.N = int(cfg.N)
        self.features: Features = features_of(cfg)
        # 켠 기능의 계수(yaml 원본). 꺼진 기능은 None 이고 그 기능의 코드 경로를 타지 않는다.
        self._fv = _food_v_params(self.features.params("food_v")) if self.features.enabled("food_v") else None
        self._sp = _speed_params(self.features.params("speed")) if self.features.enabled("speed") else None
        self._vg = (_vigil_params(self.features.params("vigilance"), cfg.fov_deg)
                    if self.features.enabled("vigilance") else None)
        self._vw = (_window_params(self.features.params("vigil_window"), self.features)
                    if self.features.enabled("vigil_window") else None)
        self._dn = (_daynight_params(self.features.params("daynight"), self.features)
                    if self.features.enabled("daynight") else None)
        self._ps = (_pred_sleep_params(self.features.params("pred_sleep"), self.features)
                    if self.features.enabled("pred_sleep") else None)
        # v3 R0: 행동 레퍼토리(repertoire), 위협 유형(threats). 둘 중 하나라도 켜면 포식자 스텝은 _step_predators_v3 다
        self._rp = (rep.parse_params(self.features.params("repertoire"), self.features)
                    if self.features.enabled("repertoire") else None)
        self._th = (_threats_params(self.features.params("threats"), self.features)
                    if self.features.enabled("threats") else None)
        self._v3p = self._rp is not None or self._th is not None
        self._rs = None
        self.act_names: tuple[str, ...] = action_names(self.features)
        self.act_dim = len(self.act_names)
        self.obs_names: tuple[str, ...] = obs_names(self.features)
        self.obs_dim = len(self.obs_names)
        # 경계 행동 열. vigilance 를 끈 세계와 v2.2r action false 세계는 None 이다(경계가 일어나지 않는다)
        self._act_vig = self.act_names.index("vigilance") if "vigilance" in self.act_names else None
        # v2.4 관측 열 (이름으로 찾는다). daynight 를 끈 세계는 None 이다
        self._obs_vis = self.obs_names.index("visibility") if self._dn is not None else None
        self._obs_tt = self.obs_names.index("to_transition") if self._dn is not None else None
        # v3 추가 관측 9칸의 첫 열 (obs_extra false 면 None)
        self._obs_rep = (self.obs_names.index(rep.OBS_EXTRA_NAMES[0])
                         if self._rp is not None and self._rp["obs_extra"] else None)
        self.reset()

    # ------------------------------------------------------------------ #
    # reset / 세계 생성
    # ------------------------------------------------------------------ #

    def reset(self) -> np.ndarray:
        """§4.4 — 시드 하나가 무작위화 파라미터와 세계 배치를 모두 결정한다 (§3.5)."""
        cfg = self.cfg
        seed = int(self.meta.choice(self.seeds))
        r = self.rng = np.random.default_rng(seed)
        self.seed = seed
        # 기능별 난수 스트림은 처음 쓸 때 만든다(feature_rng). 세계를 새로 뽑으면 처음부터 다시 시작한다.
        self._feature_rngs: dict[tuple[str, int], np.random.Generator] = {}

        rd = cfg.rand
        self.size = float(r.uniform(*rd["world_size"]))
        self.M = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
        self.pred_speed_mult = float(r.uniform(*rd["pred_speed_mult"]))
        self.ranged_frac = float(r.uniform(*rd["ranged_frac"]))
        self.cover_frac_target = float(r.uniform(*rd["cover_frac"]))
        self.food_regen_mult = float(r.uniform(*rd["food_regen_mult"]))

        self._build_world()
        if self._fv is not None:
            self._food_v_reset()
        if self._sp is not None:
            # v2.1 스텝 뒤 훅 (replay_v2): 실제 보행, 명령 보행, 적용 속도. 첫 스텝 전에는 정지·0 으로 둔다.
            self.gait = np.zeros(self.N, dtype=np.int8)
            self.gait_cmd = np.zeros(self.N, dtype=np.int8)
            self.vel = np.zeros((self.N, 2))
        if self._vg is not None:
            # v2.2 개체별 상태 (`_perceive`): threat_recency, ThreatDir(마지막 위협 방향, 단위벡터. 본 적 없으면 0),
            # 다음 관측의 시야(True = 경계 시야, 직전 스텝에 경계했다). 처음에는 모두 0·기본 시야다.
            self.threat = np.zeros(self.N)
            self.threat_dir = np.zeros((self.N, 2))
            self._wide = np.zeros(self.N, dtype=bool)
            # 통계 전용(vigil_stats *_truth, 관측·동역학에 들어가지 않는다): 결정 때 반경 안 포식자 유무(FOV 무시)와
            # 그 흔적(threat_recency 와 같은 갱신·decay·리스폰 0). 시야(경계 360°)와 무관한 기준 구간을 만든다
            self._near = np.zeros(self.N, dtype=bool)
            self._tr_truth = np.zeros(self.N)
            # 스텝 뒤 훅 (replay_v2): 이번 스텝의 경계, 시선(= 스텝 뒤 heading), 적용 속도(speed 를 끈 세계에도 둔다)
            self.vigilant = np.zeros(self.N, dtype=bool)
            self.gaze = self.head.copy()
            if self._sp is None:
                self.vel = np.zeros((self.N, 2))
        if self._vw is not None:
            # v2.2r 스텝 뒤 훅 (replay_v2): 이번 스텝의 결정 때 창, 반사 돌아보기가 heading 을 바꾼 개체
            self.window = np.zeros(self.N, dtype=bool)
            self.looked = np.zeros(self.N, dtype=bool)
        # v1 포식자 수(threats 의 플레이어 칸을 빼고). threats 를 끈 세계는 늘 self.M 과 같다
        self.M_base = self.M
        if self._v3p:
            # v3 포식자 스텝: v1 원거리형 배치(잠행형이 덮기 전, v1 스트림 호출 모양을 정한다)
            self._pred_ranged_v1 = self.pred_ranged.copy()
        if self._ps is not None:
            self._pred_sleep_reset()
        if self._th is not None:
            self._threats_reset()           # 포식자 밤잠 배치(M 개) 뒤, 어둠을 정하기 전에 잠행형·플레이어를 정한다
        if self._v3p:
            self.pred_vel = np.zeros((self.M, 2))   # 포식자의 지난 스텝 이동(관측 pred_approach)
        if self._dn is not None:
            self._daynight_reset()
        if self._rp is not None:
            self._repertoire_reset()
        self._reset_stats()
        self._g = self._geometry()
        if self._vg is not None:
            self._perceive(self._g)
        if self._rp is not None:
            rep.perceive(self._rs, self._rp, self._g)
        self._obs = self._obs_from(self._g)
        return self._obs

    def feature_rng(self, name: str, part: int = 0) -> np.random.Generator:
        """기능 `name` 의 난수 스트림. 이 세계의 시드에서 나오고 다른 기능·v1 스트림과 독립이다.

        같은 기능에 나중에 난수를 더할 때는 새 `part` 를 쓴다 (`env_v2/features.py` 규칙 3).
        """
        _check_name(name)
        _check_part(part)                   # 캐시를 찾기 전에 검사한다(True·1.0 은 키 1 과 같게 해시된다)
        key = (name, int(part))
        g = self._feature_rngs.get(key)
        if g is None:
            g = self._feature_rngs[key] = feature_stream(self.seed, name, part)
        return g

    def _build_world(self) -> None:
        cfg, r = self.cfg, self.rng
        N, size = self.N, self.size

        # --- 먹이 격자 (§4.2) ---
        # 셀마다 독립 균등난수를 깔면 먹이가 온 맵에 고르게 깔려서 따라갈 기울기가
        # 백색잡음이 된다 (측정: forage가 아무 이득이 없었다). 저주파 노이즈를
        # 문턱값으로 잘라 **패치**를 만들고, 재생은 그 용량(capacity)을 향해 간다.
        # 그래야 고갈된 패치가 비어 있는 채로 남고 먹이 탐색이 실제 문제가 된다.
        self.gw = int(np.ceil(size / cfg.food_cell))
        m = self._smooth(r.random((self.gw, self.gw)), int(cfg.food_patch_blur))
        m = (m - m.min()) / max(m.max() - m.min(), EPS)
        t = float(cfg.food_patch_threshold)
        self.food_cap = np.clip((m - t) / (1.0 - t), 0.0, 1.0)
        self.food = self.food_cap.copy()
        cc = (np.arange(self.gw) + 0.5) * cfg.food_cell      # 셀 중심 좌표
        self._cell_x, self._cell_y = np.meshgrid(cc, cc)     # 둘 다 (gw,gw)

        # --- 은신처 (§4.2): 셀 마스크 면적이 목표 비율에 닿을 때까지 원을 놓는다 ---
        centers, radii = [], []
        mask = np.zeros((self.gw, self.gw), dtype=bool)
        for _ in range(int(cfg.cover_max_count)):
            if mask.mean() >= self.cover_frac_target:
                break
            c = r.uniform(0.0, size, 2)
            rad = float(r.uniform(cfg.cover_r_min, cfg.cover_r_max))
            centers.append(c)
            radii.append(rad)
            mask |= (self._cell_x - c[0]) ** 2 + (self._cell_y - c[1]) ** 2 <= rad * rad
        self.cov_c = np.asarray(centers, dtype=np.float64).reshape(-1, 2)
        self.cov_r = np.asarray(radii, dtype=np.float64).reshape(-1)
        self.cover_cell = mask
        self.cover_frac_actual = float(mask.mean())

        # 은신처 셀은 재생 속도 0.3배 (§4.2)
        self.regen_field = cfg.food_regen_base * self.food_regen_mult * np.where(
            self.cover_cell, cfg.food_cover_regen_mult, 1.0
        )

        # --- 초식 (§4.3) ---
        self.pos = r.uniform(0.0, size, (N, 2))
        ang = r.uniform(0.0, 2 * np.pi, N)
        self.head = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy = np.full(N, float(cfg.init_energy))
        self.repro_cd = np.zeros(N, dtype=np.int32)

        # --- 포식자 (§4.2) ---
        M = self.M
        self.pred_pos = r.uniform(0.0, size, (M, 2))
        pang = r.uniform(0.0, 2 * np.pi, M)
        self.pred_head = np.stack([np.cos(pang), np.sin(pang)], 1)
        self.pred_ranged = r.random(M) < self.ranged_frac
        base = cfg.herb_speed * self.pred_speed_mult
        self.pred_speed = np.where(self.pred_ranged, base * cfg.pred_ranged_speed_mult, base)
        self.pred_catch_r = np.where(
            self.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r
        )
        # 포식 후 식사 쿨다운. §4.4가 포식자 속도를 herb_speed의 1.0~1.4배로 고정하므로
        # 한번 붙잡히면 도주로는 벗어날 수 없다. 쿨다운이 포식 압력의 상한을 정한다.
        self.pred_cd = np.zeros(M, dtype=np.int32)

        # --- 지역 피식 EMA (§3.1) ---
        self.pred_ema = 0.0
        self.t = 0

    def _left_half(self) -> np.ndarray:
        """셀 중심이 맵 왼쪽 절반(x < size/2)인 셀 (gw,gw). v2.3 지역 전까지 지역 대용이다 (계획서 0-6)."""
        return self._cell_x < 0.5 * self.size

    def _food_v_reset(self) -> None:
        """v2.0b 세계 생성 (계획서 4.9.1). v1 세계(`_build_world`)를 다 만든 뒤 부른다.

        food_v 스트림 part 0 에서 난수 정확히 3개를 이 순서로 뽑는다. 목록 길이와 상관없이 소비가 같다
        (`integers(1)` 은 난수를 소비하지 않으므로 고르기에 쓰지 않는다).
          1) u ~ U[0,1) → 회복 반감기 h = recovery_half_lives[floor(u·n)], ρ = 1 − 2^(−1/h)
          2) 왼쪽 절반 V 초기 비율 ~ U[init_frac]   3) 오른쪽 절반 ~ U[init_frac]
        V = cap0 × (그 셀이 속한 절반의 비율), F = min(v1 초기값 cap0, V). cap0 = 0 셀은 F = V = 0 이다.
        """
        fv, g = self._fv, self.feature_rng("food_v", 0)
        hl = fv["half_lives"]
        h = hl[min(int(g.random() * len(hl)), len(hl) - 1)]
        frac = g.uniform(fv["init_frac"][0], fv["init_frac"][1], 2)       # [왼쪽, 오른쪽]
        self.food_v_half_life = h
        self.food_v_rho = 1.0 - 2.0 ** (-1.0 / h)
        self.food_v_init = (float(frac[0]), float(frac[1]))
        self.food_v = self.food_cap * np.where(self._left_half(), frac[0], frac[1])
        self._fv_floor = fv["floor"] * self.food_cap
        np.minimum(self.food, self.food_v, out=self.food)
        # 기록 (food_stats·food_cells): reset 뒤 셀별 누적 섭취, 마지막으로 뜯긴 스텝(self.t, 없으면 −1)
        self._fv_eaten = np.zeros_like(self.food_cap)
        self._fv_last_eat = np.full(self.food_cap.shape, -1, dtype=np.int64)

    def _daynight_reset(self) -> None:
        """v2.4 세계 생성 (계획서 4.9.2·4.7). v1 세계(`_build_world`, t = 0)를 다 만든 뒤 부른다.

        daynight 스트림에서만 뽑는다(`daynight_draws`): part 0 에서 정확히 3개(낮 고정, T, o — 낮 고정 세계도 같은
        수를 뽑는다), start_induce > 0 이면 part 2 에서 1 + N 개. 유도된 세계는 해 지기 0.1·T 스텝 전에 시작하고
        초식 에너지가 U[0.2, 0.5]·max_energy 다. 그 뒤 t = 0 의 어둠·관측 값을 정한다(`_daynight_update`).
        """
        dn = self._dn
        dr = daynight_draws(dn, self.seed, self.N)
        self.dn_period, self.dn_offset = dr["period"], dr["offset"]
        self.dn_tw, self.day_fixed, self.dn_induced = dr["tw_steps"], dr["day_fixed"], dr["induced"]
        if dr["induced"]:
            self.energy = dr["energy"] * self.cfg.max_energy
        self._daynight_update()

    def _pred_sleep_reset(self) -> None:
        """v2.4s 세계 생성. pred_sleep 스트림 part 0 에서 1 + M 개: q ~ U[nocturnal_frac], 포식자마다 u < q 면 야행성.
        포식자 배치(`_build_world`)를 만든 뒤, 어둠을 정하는 `_daynight_reset` 전에 부른다."""
        g = self.feature_rng("pred_sleep", 0)
        lo, hi = self._ps["nocturnal_frac"]
        q = float(g.uniform(lo, hi))
        u = g.random(self.M)
        self.pred_noct_frac = q
        self.pred_nocturnal = u < q
        self.pred_asleep = np.zeros(self.M, dtype=bool)
        self._pred_speed_mult = np.ones(self.M)
        self._ps_asleep_sum, self._ps_steps = 0.0, 0

    def _threats_reset(self) -> None:
        """v3 R0 위협 유형 (명세 3절 M3·플레이어형 위협). 포식자 배치·밤잠 배치 뒤, `_daynight_reset` 전에 부른다.

        threats 스트림에서만 뽑는다:
          part 0 에서 1 + M 개: p_stalk ~ U[stalk_frac], 포식자마다 u < p_stalk 면 잠행-돌진형. 잠행형은 근접형이다 —
                  v1 이 뽑은 원거리형 배치를 덮고(v1 뽑기는 그대로, features.py 규칙 2) 속력·포획 거리를 근접형으로 둔다
          part 1 에서 4 개(늘): u < player_frac 면 플레이어가 있다, 위치 (x, y)·size, heading 각 2π·u
          part 2: 플레이어 모드를 새로 고를 때마다 2 개(`_player_new_mode`), part 3: 배회 선회(스텝마다 1 개)
        플레이어는 포식자 칸 끝(색인 M_base)에 붙는다. 밤잠 배열에는 야행성으로 넣어 잠도 박명 감속도 받지 않는다(밤에 자지 않는다).
        """
        cfg, th, Mb = self.cfg, self._th, self.M_base
        g0 = self.feature_rng("threats", 0)
        self.threat_p_stalk = float(g0.uniform(th["stalk_frac"][0], th["stalk_frac"][1]))
        stalker = g0.random(Mb) < self.threat_p_stalk
        self.pred_type = np.where(stalker, PT_STALKER, PT_CHASER).astype(np.int8)
        self.pred_ranged = self.pred_ranged & ~stalker
        base = cfg.herb_speed * self.pred_speed_mult
        self.pred_speed = np.where(self.pred_ranged, base * cfg.pred_ranged_speed_mult, base)
        self.pred_catch_r = np.where(self.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r)
        u = self.feature_rng("threats", 1).random(4)
        self.player_present = bool(u[0] < th["player_frac"])
        if self.player_present:
            ang = 2.0 * np.pi * u[3]
            self.pred_pos = np.vstack([self.pred_pos, [u[1] * self.size, u[2] * self.size]])
            self.pred_head = np.vstack([self.pred_head, [math.cos(ang), math.sin(ang)]])
            self.pred_ranged = np.append(self.pred_ranged, False)
            self._pred_ranged_v1 = np.append(self._pred_ranged_v1, False)
            self.pred_speed = np.append(self.pred_speed, 0.0)       # 플레이어 속력은 모드가 정한다
            self.pred_catch_r = np.append(self.pred_catch_r, th["player_catch_r"])
            self.pred_cd = np.append(self.pred_cd, 0).astype(np.int32)
            self.pred_type = np.append(self.pred_type, PT_PLAYER).astype(np.int8)
            if self._ps is not None:
                self.pred_nocturnal = np.append(self.pred_nocturnal, True)
                self.pred_asleep = np.append(self.pred_asleep, False)
                self._pred_speed_mult = np.append(self._pred_speed_mult, 1.0)
            self.M = Mb + 1
        self.pred_is_player = self.pred_type == PT_PLAYER
        self.stalk_state = np.zeros(self.M, dtype=np.int8)
        self.stalk_left = np.zeros(self.M, dtype=np.int64)
        self.player_mode = np.zeros(self.M, dtype=np.int8)
        self.player_left = np.zeros(self.M, dtype=np.int64)
        if self.player_present:
            self._player_new_mode(Mb)

    def _player_new_mode(self, i: int) -> None:
        """플레이어 모드를 새로 고른다(part 2 에서 2 개): u0 < player_stalk_p 면 잠행 접근, 아니면 배회. 길이 =
        하 + ⌊u1·(상 − 하 + 1)⌋ 스텝(상에서 자른다)."""
        th = self._th
        u = self.feature_rng("threats", 2).random(2)
        lo, hi = th["player_mode_steps"]
        self.player_mode[i] = PM_STALK if u[0] < th["player_stalk_p"] else PM_WANDER
        self.player_left[i] = min(lo + int(u[1] * (hi - lo + 1)), hi)

    def _repertoire_reset(self) -> None:
        """v3 R0 행동 상태 (env_v2/repertoire.py). 어둠을 정한 뒤(`_daynight_reset`) 부른다. 모든 개체가 GRAZE 진입이다."""
        rp, N = self._rp, self.N
        self._rep_gen = np.zeros(N, dtype=np.int64)               # 슬롯별 세대(리스폰 횟수) — 사건 결정 지연의 개체 키
        self._rs = rep.RepState(N, rp, self.energy / self.cfg.max_energy, self.dark, self.seed)
        self._rep_see = np.full(N, rp["graze_head_down"])         # 자기 포식자 탐지 반경 배수 (다음 관측)
        self._rep_see_last = self._rep_see.copy()                 # 직전 관측의 배수 (사건 비교 시야, `_geometry`)
        self._rep_still = np.zeros(N, dtype=bool)                 # M1 정지 (이번 스텝)
        self._rep_cover = np.ones(N)                              # 은신처 안일 때의 은신 배수 (이번 스텝)
        self._rep_eat = np.zeros(N)                               # 섭식·대사 배수 (이번 스텝, 제어기)
        self._rep_drain = np.ones(N)
        self._rep_a4 = np.zeros((N, ACT_DIM))                     # v1 stats() 의 행동 열 자리(레퍼토리 세계는 0)
        self._rep_export()

    def _rep_export(self) -> None:
        """스텝 뒤 훅 (애니메이션 계약, 언리얼이 받는 넷): 이번 스텝에 실행한 행동·위상·경과·seq 의 사본. 리스폰은 바꾸지
        않는다(죽은 슬롯의 마지막 프레임이 그 개체의 값이다, replay_v2 규약). 새 개체의 상태는 다음 스텝 값부터다."""
        rs = self._rs
        self.behavior = rs.behavior.copy()
        self.beh_phase = rs.phase.copy()
        self.beh_steps = rs.steps_in.copy()
        self.beh_seq = rs.seq.copy()

    def rep_obs_extra(self) -> np.ndarray:
        """v3 추가 관측 9칸 (N, 9) float32 — 지금 관측(스텝 끝 기하)과 같은 때의 값. obs_extra 가 false 여도 계산한다
        (R1 학습·손 규칙용). 순서는 `repertoire.OBS_EXTRA_NAMES`."""
        if self._rp is None:
            raise ValueError("rep_obs_extra 는 repertoire 를 켠 세계에만 있다")
        return rep.obs_extra(self._rs, self._rp, self._g)

    def _daynight_update(self) -> None:
        """지금 t 의 어둠 d·실효 탐지 반경·관측 두 칸 (계획서 4.9.2, 4.2). reset 과 `step` 의 t 증가 뒤에 부른다.

        여기서 정한 값을 그 뒤 관측(8)과 다음 스텝의 동역학(섭식·휴식 대사)이 함께 쓴다 — 결정 때 값이다.
        visibility = 1 − detect_night·d (날씨 w 는 v2.6, 지금 1), to_transition = min(r / transition_norm, 1).
        낮 고정 세계는 d = 0, 반경 see_r, 관측 1·1 (중립값, 계획서 4.2)이다.
        """
        dn = self._dn
        if self.day_fixed:
            d, tt = 0.0, 1.0
        else:
            d, r = daynight_phase(self.t, self.dn_period, self.dn_offset, self.dn_tw)
            tt = min(r / dn["transition_norm"], 1.0)
        self.dark = d
        self._vis = 1.0 - dn["detect_night"] * d
        self._to_tr = tt
        self._see_pred = self.cfg.see_r * self._vis
        if self._ps is not None:        # v2.4s: 주행성 포식자의 잠·박명 감속 (결정 때 어둠, 다음 스텝 포식자 이동에 쓴다)
            ps = self._ps
            diurnal = ~self.pred_nocturnal
            self.pred_asleep = diurnal & (d >= ps["sleep_dark"])
            slow = (1.0 - d) if ps["twilight_slow"] else 1.0
            self._pred_speed_mult = np.where(self.pred_asleep, 0.0, np.where(diurnal, slow, 1.0))

    # ------------------------------------------------------------------ #
    # 기하 (관측과 조향이 공유한다)
    # ------------------------------------------------------------------ #

    def _smooth(self, arr: np.ndarray, br: int) -> np.ndarray:
        """반경 br 셀 박스 평균. SAT를 새로 만든다 (reset 시 1회용)."""
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(arr, 0), 1, out=sat[1:, 1:])
        return self._box_mean(sat, max(1, br))

    def _box_mean(self, sat: np.ndarray, br: int) -> np.ndarray:
        """SAT에서 반경 br 셀 정사각 평균. 경계는 잘린 창의 실제 면적으로 나눈다."""
        g = self.gw
        i = np.arange(g)
        r0, r1 = np.clip(i - br, 0, g), np.clip(i + br + 1, 0, g)
        c0, c1 = r0, r1  # 정방 격자라 행/열 인덱스가 같다
        box = (
            sat[np.ix_(r1, c1)] - sat[np.ix_(r0, c1)] - sat[np.ix_(r1, c0)] + sat[np.ix_(r0, c0)]
        )
        return box / ((r1 - r0)[:, None] * (c1 - c0)[None, :])

    def _food_fields(self) -> None:
        """먹이 밀도(관측용)와 기울기(조향용)를 격자 전체에 대해 한 번 계산한다.

        두 필드의 블러 반경이 **다르다**. 일부러 그렇게 뒀다:

        - `food_blur` (관측 idx0): 반경 `see_r`. §9.4의
          `IWorldFoodProvider::GetFoodDensity(Location, Radius)` 와 맞추기 위한 반경 평균이다
          (각도 제한 없음 — 언리얼 인터페이스가 반경만 받는다).
        - `_food_g*` (조향 `food_grad`): 반경 `food_grad_blur` 셀. see_r 블러(11×11셀)에서
          기울기를 뽑으면 한 셀을 먹어치워도 값이 0.8%밖에 안 변해서, 개체 전원이 초기
          고밀도 지점으로 몰린 뒤 같은 셀을 두고 경쟁한다. 측정 결과 `forage=1`이
          `forage=0`보다 **덜 먹었다**. 좁은 반경을 쓰면 국소 고갈이 기울기에 바로 잡혀
          비어버린 주변을 벗어나는 방향을 가리킨다.

        `food_grad` 는 관측이 아니라 §3.3의 기하 입력이므로 이 분리가 §3 계약을 건드리지
        않는다. 언리얼도 `GetFoodDensity` 와 `FoodGrad` 를 별도로 제공한다 (§9.4/§9.5).
        """
        cfg = self.cfg
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(self.food, 0), 1, out=sat[1:, 1:])
        self.food_blur = self._box_mean(sat, max(1, int(round(cfg.see_r / cfg.food_cell))))
        gy, gx = np.gradient(self._box_mean(sat, max(1, int(cfg.food_grad_blur))))
        self._food_gx, self._food_gy = gx, gy

    def _cover_edge(self, p: np.ndarray):
        """은신처 원까지의 (dx, dy, 가장자리까지 거리) — 전부 (n,K)."""
        dx = self.cov_c[:, 0][None, :] - p[:, 0:1]
        dy = self.cov_c[:, 1][None, :] - p[:, 1:2]
        return dx, dy, np.sqrt(dx * dx + dy * dy) - self.cov_r[None, :]

    def _in_cover(self, p: np.ndarray) -> np.ndarray:
        """위치 `p` (n,2)가 은신처 원 안인가. 관측과 포식자 판정이 같은 정의를 쓴다."""
        if not len(self.cov_r):
            return np.zeros(len(p), dtype=bool)
        return self._cover_edge(p)[2].min(1) <= 0.0

    def _cell_index(self, p: np.ndarray):
        """월드 좌표 → 격자 인덱스 (ix=열, iy=행)."""
        k = 1.0 / self.cfg.food_cell
        ix = np.clip((p[:, 0] * k).astype(np.int32), 0, self.gw - 1)
        iy = np.clip((p[:, 1] * k).astype(np.int32), 0, self.gw - 1)
        return ix, iy

    def _geometry(self, idx: np.ndarray | None = None, out: dict | None = None) -> dict:
        """행 `idx` (None이면 전체)의 기하 정보를 계산한다.

        `out` 을 주면 그 딕셔너리의 해당 행만 덮어쓴다 (§4.5 `_observe_subset` 경로).
        """
        cfg = self.cfg
        if idx is None:
            idx = np.arange(self.N)
            self._food_fields()
        P = self.pos[idx]
        Hd = self.head[idx]
        n = len(idx)
        ar = np.arange(n)
        hx, hy = Hd[:, 0:1], Hd[:, 1:2]
        # 시야각 판정 문턱 cos(FOV/2). v2.2: 직전 스텝에 경계한 개체(self._wide)는 경계 시야(360° 면 −inf, 각도 판정
        # 없음)로 동족·포식자를 본다 — 관측 1·2·3 과 조향 기하(to_centroid·away_from_pred·d_pred_min)가 함께 넓어진다.
        # 반경은 see_r 그대로다(#5). vigilance 를 끈 세계는 v1 과 같은 스칼라 비교다.
        fov_cos = (cfg.fov_cos if self._vg is None else
                   np.where(self._wide[idx], self._vg["wide_cos"], cfg.fov_cos)[:, None])

        # 쌍별 계산은 전부 (n, ·) 2D로 둔다. (n,N,2) 3D 임시배열을 만들면 스텝의 75%를
        # 여기서 쓴다 (측정). 합산은 행렬곱으로 내려보낸다.

        # --- 동족: 시야(거리 + 각도) 내, 자기 제외 (§3.1 idx3) ---
        dx = self.pos[:, 0][None, :] - P[:, 0:1]
        dy = self.pos[:, 1][None, :] - P[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        kin_vis = (dist <= cfg.see_r) & ((dx * hx + dy * hy) * invd >= fov_cos)
        kin_vis[ar, idx] = False
        kin_f = kin_vis.astype(np.float64)
        kin_count = kin_f.sum(1)
        centroid = (kin_f @ self.pos) / np.maximum(kin_count, 1.0)[:, None]
        to_centroid = np.where(kin_count[:, None] > 0, normalize(centroid - P), 0.0)

        # --- separation: 반경 내 이웃마다 (1 - d/R) * 멀어지는 단위벡터, 합 후 크기 1로 clamp ---
        # sum_j w_ij * (pos_j - P_i)/d_ij  =  (c @ pos) - rowsum(c) * P,  c = w/d
        wgt = np.clip(1.0 - dist / cfg.sep_radius, 0.0, None)
        wgt[ar, idx] = 0.0
        c = wgt * invd
        separation = clamp_magnitude(-((c @ self.pos) - c.sum(1)[:, None] * P), 1.0)

        # --- 포식자 (§3.1 idx1, idx2) ---
        if self.M > 0:
            ex = self.pred_pos[:, 0][None, :] - P[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - P[:, 1:2]
            pd = np.sqrt(ex * ex + ey * ey)
            pinv = 1.0 / np.maximum(pd, EPS)
            # v2.4: 초식의 포식자 탐지 반경만 see_r·(1 − detect_night·d) 로 준다(계획서 4.9.2 (a)). 동족 시야(위)·관측 2 의
            # 분모·조향 도주 문턱(steering.py)은 see_r 그대로다. d = 0 이면 see_r·1.0 이라 v2.1 과 비트 단위로 같다
            see_p = cfg.see_r if self._dn is None else self._see_pred
            if self._rp is not None:    # v3: 개체 행동별 자기 탐지 반경(GRAZE 고개 숙임 M5, SLEEP 시야)
                see_p = see_p * self._rep_see[idx][:, None]
            pvis = (pd <= see_p) & ((ex * hx + ey * hy) * pinv >= fov_cos)
            if self._ps is not None:    # v2.4s: 자는 포식자는 굴에 있어 보이지 않는다(관측 1·2·도주 조향에서 빠진다)
                pvis &= ~self.pred_asleep[None, :]
            pred_count = pvis.sum(1)
            masked = np.where(pvis, pd, np.inf)
            j = masked.argmin(1)
            d_pred_min = masked[ar, j]
            seen = np.isfinite(d_pred_min)[:, None]
            away = np.where(
                seen, -np.stack([ex[ar, j], ey[ar, j]], 1) * pinv[ar, j][:, None], 0.0
            )
        else:
            pred_count = np.zeros(n, dtype=np.int64)
            d_pred_min = np.full(n, np.inf)
            away = np.zeros((n, 2))

        # --- 은신처 (§3.1 idx6) ---
        if len(self.cov_r):
            cx, cy, edge = self._cover_edge(P)
            k = edge.argmin(1)
            e = edge[ar, k]
            in_cover = e <= 0.0
            cover_dist = np.clip(np.maximum(e, 0.0) / cfg.obs_cover_norm, 0.0, 1.0)
            to_cover = np.where(
                in_cover[:, None], 0.0, normalize(np.stack([cx[ar, k], cy[ar, k]], 1))
            )
        else:
            in_cover = np.zeros(n, dtype=bool)
            cover_dist = np.ones(n)
            to_cover = np.zeros((n, 2))

        # --- 먹이 (§3.1 idx0) ---
        ix, iy = self._cell_index(P)
        food_density = self.food_blur[iy, ix]
        food_grad = normalize(np.stack([self._food_gx[iy, ix], self._food_gy[iy, ix]], 1))

        vals = dict(
            food_grad=food_grad,
            food_density=food_density,
            to_centroid=to_centroid,
            kin_count=kin_count,
            separation=separation,
            d_pred_min=d_pred_min,
            pred_count=pred_count,
            away_from_pred=away,
            to_cover=to_cover,
            cover_dist=cover_dist,
            in_cover=in_cover,
        )
        if self._rp is not None:
            # v3 (repertoire 관측·사건 입력): 가장 가까운 보이는 위협의 접근 속력 c = clip(v_pred·û / herb_speed, −1, 1)
            # (û = 위협에서 이 개체 쪽 단위벡터, v_pred = 그 위협의 지난 스텝 이동)를 (c + 1)/2 로, 없으면 0.5.
            # kin_alarm = 보이는 동족 중 FLEE 비율(없으면 0). cover_k = 가장 가까운 은신처 색인(가장자리 거리, 동점이면 낮은
            # 색인, 은신처가 없으면 −1).
            # *_ev = 사건 비교 시야(이번 관측과 직전 관측의 행동 시야 배수 중 작은 쪽)로 센 포식자 수·가장 가까운 거리·접근 속력.
            # 사건 E1·E2 만 쓴다 — 자기 행동이 바뀌어 시야가 넓어진 것만으로 생긴 위협은 사건이 아니다(repertoire docstring A.b)
            if self.M > 0:
                pv = self.pred_vel[j]
                c = -(pv[:, 0] * ex[ar, j] + pv[:, 1] * ey[ar, j]) * pinv[ar, j] / cfg.herb_speed
                vals["pred_approach"] = np.where(seen[:, 0], (np.clip(c, -1.0, 1.0) + 1.0) * 0.5, 0.5)
                lo = np.minimum(self._rep_see[idx], self._rep_see_last[idx])
                base_r = cfg.see_r if self._dn is None else self._see_pred
                pvis_e = pvis & (pd <= base_r * lo[:, None])
                masked_e = np.where(pvis_e, pd, np.inf)
                je = masked_e.argmin(1)
                seen_e = np.isfinite(masked_e[ar, je])
                pve = self.pred_vel[je]
                ce = -(pve[:, 0] * ex[ar, je] + pve[:, 1] * ey[ar, je]) * pinv[ar, je] / cfg.herb_speed
                vals["pred_count_ev"] = pvis_e.sum(1)
                vals["d_pred_min_ev"] = masked_e[ar, je]
                vals["pred_approach_ev"] = np.where(seen_e, (np.clip(ce, -1.0, 1.0) + 1.0) * 0.5, 0.5)
            else:
                vals["pred_approach"] = np.full(n, 0.5)
                vals["pred_count_ev"] = np.zeros(n, dtype=np.int64)
                vals["d_pred_min_ev"] = np.full(n, np.inf)
                vals["pred_approach_ev"] = np.full(n, 0.5)
            flee = (self._rs.behavior == rep.FLEE).astype(np.float64)
            vals["kin_alarm"] = np.where(kin_count > 0, (kin_f @ flee) / np.maximum(kin_count, 1.0), 0.0)
            vals["cover_k"] = k if len(self.cov_r) else np.full(n, -1, dtype=np.int64)
        if out is None:
            return vals
        for key, v in vals.items():
            out[key][idx] = v
        return out

    # ------------------------------------------------------------------ #
    # 관측 (§3.1)
    # ------------------------------------------------------------------ #

    def _obs_from(self, g: dict, idx: np.ndarray | None = None) -> np.ndarray:
        """§3.1 — v1 7개(+ 켠 기능의 칸, `obs_names`), float32, [0,1]. 정규화 상수는 전부 고정값이다 (§1.2).

        v2.2 idx 7 threat_recency 는 `_perceive` 가 이 관측의 기하로 갱신한 값 그대로다(이미 [0,1]).
        """
        cfg = self.cfg
        sl = slice(None) if idx is None else idx
        n = self.N if idx is None else len(idx)
        o = np.empty((n, self.obs_dim), dtype=np.float32)
        o[:, OBS_FOOD_DENSITY] = np.clip(g["food_density"][sl], 0.0, 1.0)
        o[:, OBS_PREDATOR_COUNT] = np.clip(g["pred_count"][sl] / cfg.obs_pred_count_norm, 0.0, 1.0)
        o[:, OBS_PREDATOR_DISTANCE] = np.clip(g["d_pred_min"][sl] / cfg.see_r, 0.0, 1.0)
        o[:, OBS_KIN_COUNT] = np.clip(g["kin_count"][sl] / cfg.obs_kin_count_norm, 0.0, 1.0)
        o[:, OBS_ENERGY] = np.clip(self.energy[sl] / cfg.max_energy, 0.0, 1.0)
        o[:, OBS_RECENT_PREDATION] = min(self.pred_ema, 1.0)
        o[:, OBS_COVER_DISTANCE] = g["cover_dist"][sl]
        if self._vg is not None:
            o[:, OBS_THREAT_RECENCY] = self.threat[sl]
        if self._dn is not None:        # v2.4 전역 값 두 칸 (계획서 4.2 visibility·to_transition, 이미 [0,1])
            o[:, self._obs_vis] = self._vis
            o[:, self._obs_tt] = self._to_tr
        if self._obs_rep is not None:   # v3 추가 관측 9칸 (obs_extra true 일 때만)
            o[:, self._obs_rep:self._obs_rep + len(rep.OBS_EXTRA_NAMES)] = rep.obs_extra(self._rs, self._rp, g, idx)
        return o

    def _observe_subset(self, idx: np.ndarray) -> np.ndarray:
        """§4.5 — 리스폰된 슬롯만 재계산한다. v2.2 는 리스폰이 0 으로 되돌린 threat_recency 를 이 관측으로 갱신한다."""
        self._geometry(idx, out=self._g)
        if self._vg is not None:
            self._perceive(self._g, idx)
        if self._rp is not None:
            rep.perceive(self._rs, self._rp, self._g, idx)
        return self._obs_from(self._g, idx)

    def _perceive(self, g: dict, idx: np.ndarray | None = None) -> None:
        """v2.2 threat_recency·ThreatDir 갱신 (계획서 4.2 idx 7, 4.4). 관측을 만들 때마다 개체당 한 번 부른다.

        '보임' = 이 관측의 포식자 수(관측 1)가 0 보다 크다 — 기본 FOV 120°, 직전 스텝에 경계한 개체는 경계 시야
        (`_geometry`). 반경은 see_r 그대로다.
          r ← 1                  (보임)
          r ← decay · r          (안 보임)
          ThreatDir ← 가장 가까운 보이는 포식자 쪽 단위벡터 (= −away_from_pred. 보일 때만 바꾸고 안 보이면 그대로)
        부르는 때: reset(r = 0·ThreatDir = 0 에서 첫 관측으로), 스텝 끝 8) 관측(스텝마다 한 번 → 놓친 뒤 k 스텝이면
        r = decay^k), 리스폰(`_respawn` 이 r = 0·ThreatDir = 0 으로 되돌린 뒤 리스폰 관측으로. 리스폰 자리에서 포식자가
        보이면 1, 아니면 0). 죽은 개체의 terminal_obs 는 리스폰 전 값(죽은 스텝 끝 관측)이다.
        C++ 꼴: Recency = (PredCount > 0) ? 1 : Decay * Recency; if (PredCount > 0) ThreatDir = ToNearestPred.

        같은 때에 통계 전용 기준 상태도 갱신한다(관측·동역학에 들어가지 않는다, C++ 로 옮기지 않는다):
        `_near` = 이 관측 위치에서 거리 ≤ see_r 인 포식자가 있다(FOV 무시, `_geometry` 와 같은 거리 식이라
        보임 ⇒ 반경 안), `_tr_truth` = 같은 규칙의 흔적(반경 안이면 1, 아니면 × decay, 리스폰 0).
        """
        sl = slice(None) if idx is None else idx
        decay = self._vg["decay"]
        seen = g["pred_count"][sl] > 0
        r = self.threat[sl] * decay
        r[seen] = 1.0
        self.threat[sl] = r
        td = self.threat_dir[sl]
        td[seen] = -g["away_from_pred"][sl][seen]
        self.threat_dir[sl] = td
        P = self.pos[sl]
        if self.M > 0:
            ex = self.pred_pos[:, 0][None, :] - P[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - P[:, 1:2]
            near = (np.sqrt(ex * ex + ey * ey) <= self.cfg.see_r).any(1)
        else:
            near = np.zeros(len(P), dtype=bool)
        tr = self._tr_truth[sl] * decay
        tr[near] = 1.0
        self._tr_truth[sl] = tr
        self._near[sl] = near

    def observe(self) -> np.ndarray:
        return self._obs

    # ------------------------------------------------------------------ #
    # step (§4.5)
    # ------------------------------------------------------------------ #

    def _check_action(self, a: np.ndarray) -> None:
        """행동 배열 모양 (N, act_dim). 행동 4개(v1)를 speed·vigilance 를 켠 세계에 넣으면 그 열이 없어 여기서 멈춘다."""
        if a.ndim != 2 or a.shape != (self.N, self.act_dim):
            raise ValueError(
                f"행동은 ({self.N}, {self.act_dim}) [{', '.join(self.act_names)}] 이어야 한다. 받은 모양: {a.shape}"
                + (". v1 정책(Utility·random 4개)은 speed 를 켠 세계에 그대로 쓸 수 없다" if self.act_dim != ACT_DIM
                   and a.ndim == 2 and a.shape[1] == ACT_DIM else ""))

    def step(self, a: np.ndarray):
        """`a`: (N, act_dim) in [0,1] (§1.3). act_dim 은 v1 4, speed 를 켜면 5, vigilance 까지 켜면 6.
        repertoire(v3)를 켜면 act_dim 1 이고 값은 정수 행동 번호(0..4)다(정수가 아니면 ValueError).
        반환: obs, reward, done, terminal_obs.

        speed(v2.1)를 켠 세계의 스텝 순서는 `_gait_step`, vigilance(v2.2)는 `_vigil_step`, repertoire(v3)는
        env_v2/repertoire.py 모듈 docstring 과 `_rep_step` 에 적었다. 끈 세계는 v1 과 같은 줄을 탄다.
        """
        cfg = self.cfg
        a = np.asarray(a, dtype=np.float64)
        self._check_action(a)
        rew = np.full(self.N, cfg.rew_alive)
        vg, vw, rp = self._vg, self._vw, self._rp
        if vg is not None:
            ema0 = min(self.pred_ema, 1.0)              # 결정 때 관측 5 (vigil_stats B5′ 용, 6) 에서 바뀐다)
        if vw is not None:              # v2.2r 0) 결정 때 창: 결정 관측의 포식자 수 0 & threat_recency > theta
            self.window = (self._g["pred_count"] == 0) & (self.threat > vw["theta"])

        if rp is not None:
            # v3 0r·1r) 행동 실행기: 결정 시점에만 요청을 받고(잠금·사건·지연), 행동별 제어기가 속도·보행을 정한다
            v, rep_out = self._rep_step(a)
        else:
            # 1) 초식 이동 — §3.3 조향 수식. 벽 경계(§4.2), 토러스 없음.
            #    v2.2 threat_flee > 0 (#18 변형, Gate E2b 보고 팔)만 위협 반대 항을 정규화 전에 더한다. 0 이면 None 이라
            #    steer 가 v1 줄 그대로다.
            v = steer(self._g, a, cfg,
                      self._threat_flee_term() if vg is not None and vg["threat_flee"] > 0.0 else None)
            if self._sp is not None:
                v = self._gait_step(v, a[:, ACT_SPEED])     # v2.1: 보행 상태가 크기만 바꾼다. 방향은 v1 조향 그대로
            if self._act_vig is not None:       # v2.2: 경계면 속력 0 (speed 보다 우선). v2.2r W′ 는 창 안에서만
                v = self._vigil_step(v, a[:, self._act_vig],
                                     self.window if vw is not None and vw["window_only"] else None)
        self.pos = np.clip(self.pos + v, 0.0, self.size)
        moving = np.linalg.norm(v, axis=1) > EPS
        self.head = np.where(moving[:, None], normalize(v), self.head)
        if rp is not None:                  # v3: FREEZE 는 위협 쪽을 본다(모르면 그대로)
            face = (rep_out["face"] != 0.0).any(1)
            self.head[face] = rep_out["face"][face]
        if vg is not None:                  # v2.2 1e): 경계한 개체는 위협 쪽을 본다(ThreatDir, 본 적 없으면 유지)
            self._face_threat()
        if vw is not None and vw["look_back"]:   # v2.2r 1f): 정지 중이고 창 안이면 위협 쪽을 본다(L 반사)
            self._look_back()

        # 2) 포식자 이동 + 포획 판정 (v3 는 정지 탐지·상태별 은신 배수·잠행형·플레이어)
        caught = self._step_predators_v3() if self._v3p else self._step_predators()

        # 3) 섭식 · 대사 (§3.4 "에너지 획득 +1.0 × 획득량")
        if self._sp is None and vg is None and self._dn is None:
            e_drained = self.energy - cfg.energy_drain
            gain = self._eat(e_drained)
        else:                       # v2.1·v2.2·v2.4: 대사와 섭식 배수가 이번 스텝의 실제 보행·경계·어둠을 따른다
            drain, eat = self._drain_eat()
            e_drained = self.energy - drain
            gain = self._eat(e_drained, eat)
        e_new = np.minimum(e_drained + gain * cfg.food_energy_per_unit, cfg.max_energy)
        if self._sp is not None and self._sp["net_energy_reward"]:
            # #4 순변화 e_new − e_prev. 번식 리셋(아래 4)과 리스폰(8)은 이 뒤라 들어가지 않는다
            rew += cfg.rew_energy * (e_new - self.energy)
        else:
            rew += cfg.rew_energy * (e_new - e_drained)
        e_prev = self.energy
        self.energy = e_new

        # 4) 번식 — energy > threshold AND repro_cd == 0 (§3.4)
        self.repro_cd = np.maximum(self.repro_cd - 1, 0)
        repro = (self.energy > cfg.repro_threshold) & (self.repro_cd == 0)
        if repro.any():
            rew += cfg.rew_repro * repro
            self.energy = np.where(repro, cfg.init_energy, self.energy)
            self.repro_cd = np.where(repro, int(cfg.repro_cd), self.repro_cd)

        # 5) 사망: 피식 또는 아사
        starved = self.energy <= 0.0
        done = caught | starved
        rew += cfg.rew_death * done

        # 6) 지역 피식 EMA (§3.1). §9.6과 맞춰 피식 사망만 센다.
        n_pred_deaths = int(caught.sum())
        self.pred_ema = (
            cfg.predation_ema_decay * self.pred_ema
            + (1.0 - cfg.predation_ema_decay) * (n_pred_deaths / self.N) * cfg.predation_ema_gain
        )

        # 7) 먹이 재생 (§4.2). 셀 용량(패치 구조)을 향해 자란다.
        #    은신처 셀은 이미 0.3배가 반영된 regen_field.
        if self._fv is None:
            self.food += self.regen_field * (self.food_cap - self.food)
            np.clip(self.food, 0.0, self.food_cap, out=self.food)
        else:
            self._food_v_step()        # v2.0b: 훼손 → 재생(목표·상한 V) → 휴식 회복

        self.t += 1
        self._accumulate(a if rp is None else self._rep_a4, rew, repro, caught, starved, done)
        if rp is not None:            # v3: 결정 때 상태(어둠·위협 보임)와 이번 스텝 행동으로 레퍼토리 지표를 센 뒤 시간을 넘긴다
            self._rep_accumulate(rep_out, caught, starved)
            self._rep_export()
            rep.tick(self._rs)
        if self._sp is not None:      # 스텝 전 기하(self._g)·결정 때 에너지로 보행 지표를 센다
            self._gait_accumulate(e_prev, e_new - e_drained, drain)
        if vw is not None:            # 결정 때 창·배부름으로 창 지표(B3_L·W′ 사용률)를 센다
            self._window_accumulate(e_prev)
        if vg is not None:            # 결정 때 상태(기하·threat_recency·시야·에너지)로 경계 지표를 센다
            flee = self._vigil_accumulate(a, e_prev, ema0, moving)
            self._wide = self.vigilant.copy()       # 8a) 이번 스텝에 경계한 개체의 다음 관측은 경계 시야다
        if self._dn is not None:
            # v2.4: 결정 때 어둠(이번 스텝 동역학의 d)으로 위상 지표를 센 뒤, 새 t 의 어둠·탐지 반경·관측 값을 정한다.
            # 아래 8) 의 기하·관측과 다음 스텝의 섭식·휴식 대사가 이 값을 쓴다
            self._daynight_accumulate(e_prev, caught, starved, e_new - e_drained, drain)
            self._daynight_update()

        # 8) 관측 — 스텝당 observe() 한 번 (§4.5)
        g = self._geometry()
        if vg is not None:
            self._perceive(g)                       # 8b) threat_recency·ThreatDir
            if vg["fov_deg"] >= 360.0:              # 8c) 360° 경계 시야로 새로 찾은 포식자 쪽을 본다 (4.4 경계 행)
                self._face_threat()
            self._b4_accumulate(flee, g, done)
        if rp is not None:
            rep.perceive(self._rs, rp, g)           # v3: 마지막 위협 방향·threat_recency
        obs = self._obs_from(g)
        self._g, self._obs = g, obs
        terminal_obs = obs.copy()
        if done.any():
            dead = np.flatnonzero(done)
            self._respawn(dead)
            obs[dead] = self._observe_subset(dead)
            if self._sp is not None:
                self._gait_prev[:, dead] = -1     # 새 개체: 보행 전환(B8)을 이전 개체와 잇지 않는다
            if vg is not None:
                self._vig_prev[dead] = -1         # 새 개체: 경계 전환(b8_vig)도 잇지 않는다

        return obs, rew, done, terminal_obs

    def _drain_eat(self) -> tuple[np.ndarray, np.ndarray]:
        """`step` 3) 의 개체별 (대사, 섭식 배수). speed·vigilance 중 하나라도 켠 세계에서만 부른다.

        - speed: 대사 energy_drain × drain_mult[실제 보행], 섭식 gait_eat[실제 보행] (v2.1 그대로)
        - speed 를 끈 세계: 대사 energy_drain(v1), 섭식 1 (v1 그대로. 보행이 없어 대사가 속력과 무관하다)
        - vigilance: 경계한 개체의 섭식 배수만 eat_mult 로 바꾼다. 대사는 바꾸지 않는다 — 경계 개체의 실제 보행은
          정지(`_vigil_step`)라 speed 세계에서는 정지 대사 c_rest(= drain_mult[정지]), speed 를 끈 세계에서는 v1 대사다
        """
        cfg = self.cfg
        if self._rp is not None:
            # v3 (명세 2절 표): 대사·섭식 배수는 행동 제어기(`repertoire.control`)가 정한다 — 대사 = 보행 대사, SLEEP 이고
            # 은신처 안이면 × (1 − sleep_rest·d)(휴식 할인은 SLEEP 전용이라 daynight.rest_night 는 쓰지 않는다), 섭식 =
            # GRAZE 정지 1·걷기 0.5, 그 밖 0. 섭식에는 밤 배수 (1 − eat_night·d) 를 곱한다.
            # C++ 꼴: Drain = EnergyDrain * DrainMult(B, G, bInCover, D); Want *= EatMult(B, G) * (1 − EatNight·D)
            return cfg.energy_drain * self._rep_drain, self._rep_eat * (1.0 - self._dn["eat_night"] * self.dark)
        if self._sp is not None:
            drain = cfg.energy_drain * self._sp["drain_mult"][self.gait]
            eat = self._sp["eat"][self.gait]
        else:
            drain = np.full(self.N, cfg.energy_drain)
            eat = np.ones(self.N)
        if self._vg is not None:
            eat = np.where(self.vigilant, self._vg["eat_mult"], eat)
        if self._dn is not None:
            # v2.4 (계획서 4.9.2 (b)(c)): 결정 때 어둠 d 로 섭식 × (1 − eat_night·d), 정지·비경계 개체의 대사 ×
            # (1 − rest_night·d). 정지에는 방향이 없어 멈춘 개체(stall)도 든다. d = 0 이면 × 1.0 이라 v2.1 과 같다.
            # C++ 꼴: Want *= GaitEat[G] * (1 − EatNight·D); Drain = EnergyDrain * DrainMult[G] * (bRest ? 1 − RestNight·D : 1)
            dn, d = self._dn, self.dark
            eat = eat * (1.0 - dn["eat_night"] * d)
            rest = self.gait == GAIT_STOP
            if self._vg is not None:
                rest = rest & ~self.vigilant
            if dn["rest_cover_only"]:       # v2.4b: 은신처 안에서 멈춘 개체만(정지 개체는 움직이지 않아 결정 때 위치 그대로)
                rest = rest & self._g["in_cover"]
            drain = np.where(rest, drain * (1.0 - dn["rest_night"] * d), drain)
        return drain, eat

    def _vigil_step(self, v: np.ndarray, a_vig: np.ndarray, win: np.ndarray | None = None) -> np.ndarray:
        """v2.2 경계 (계획서 4.3·4.4 1단계 표, #1·#5). `step` 1) 에서 보행(`_gait_step`) 뒤에 부른다.

        v2.2r W′(vigil_window.window_only)면 `win`(결정 때 창, `step` 0)을 받아 1a') 를 vig = a_vig > threshold & win
        으로 바꾼다 — 창 밖에서는 경계가 효력이 없고 speed 가 보행을 정한다. 나머지 순서는 아래 그대로다.
        C++ 꼴: bVig = A[Vig] > Threshold && (!bWindowOnly || bWindow).

        한 스텝 순서 — C++ 로 옮길 때 이 순서를 지킨다. 행동 쪽은 상태가 없다(문턱 고정, 최소 유지 시간 없음):
          1-)  (step, threat_flee > 0 일 때만) v1 조향 합에 #18 위협 반대 항을 더한 뒤 정규화한다(`_threat_flee_term`).
               threat_flee = 0(configs/v2_2.yaml)이면 이 단계가 없다
          1a') 경계 vig = a_vig > threshold (sigmoid 뒤 [0,1] 값. 같으면 경계가 아니다)
          1b') 경계면 v ← 0 — speed 명령보다 우선한다. speed 세계에서는 실제 보행 gait ← 정지(gait_cmd 는 speed 명령
               그대로). 그래서 대사는 정지 대사, 섭식은 eat_mult(`_drain_eat`)다
          1d)  (step) pos ← clip(pos + v), |v| > EPS 면 heading ← v 방향 — v1 줄 그대로. 경계는 v = 0 이라 여기서는 유지
          1e)  (step) 경계면 heading ← ThreatDir (단위벡터, 0 이면 유지, `_face_threat`). ThreatDir 는 결정 때 관측
               (이전 스텝 끝 8b)에서 갱신했으므로 '결정 때 포식자가 보였으면 가장 가까운 포식자 쪽, 아니면 마지막 위협
               방향'이다
          2)~7) (step) 포식자·섭식·대사·번식·사망·재생. 포식자는 경계를 모른다(v1 그대로)
          8a)  (step) 다음 관측의 시야 ← vig. 경계한 개체는 시야각 fov_deg(360°)·반경 see_r 로 동족·포식자를 본다
               (관측 1·2·3·조향 기하). 리스폰 개체는 기본 시야로 되돌린다(`_respawn`)
          8b)  (step) threat_recency·ThreatDir 갱신 (`_perceive`)
          8c)  (step, fov_deg = 360 일 때만) 경계면 heading ← ThreatDir 를 한 번 더 한다(`_face_threat`, 리스폰 전).
               8b 가 360° 경계 시야로 새로 찾은 포식자(경계를 시작한 스텝의 결정 관측 120° 로는 안 보이던 뒤쪽 포식자
               포함) 쪽을 스텝 끝 heading 으로 남긴다 — 4.4 경계 행 '보이면 가장 가까운 포식자 쪽'. 360° 시야의
               기하는 heading 을 쓰지 않으므로(각도 판정 −inf) 이미 만든 관측이 그대로 맞다. fov_deg < 360 이면 하지
               않는다(heading 을 바꾸면 그 heading 으로 잰 관측과 어긋난다). 그때 스텝 끝 heading 은 1e 의 값이고,
               그 스텝에 처음 본 포식자 쪽은 다음 경계 스텝의 1e 에서 돈다
        경계 중 FOV 가 360° 라 바라보는 방향은 그 스텝의 탐지에 영향이 없다(4.4 '위협 쪽 보기는 연출'). 다만 경계를
        풀고 멈춰 서면 heading 이 유지되므로 그때의 120° 시야는 마지막 경계 스텝 끝에 본 위협 쪽을 향한다(8c. 한 스텝짜리
        경계도 그 스텝에 360° 로 찾은 포식자 쪽을 남긴다). fov_deg = 360 에서 스텝 끝 heading 은 8c 만으로 정해지고
        1e 는 2)~8b 사이의 중간 값만 바꾼다(그 사이에 heading 을 읽는 단계가 없다).
        C++ 꼴: bVig = A[Vig] > Threshold; if (bVig) { Velocity = 0; Gait = Stop; if (!ThreatDir.IsZero())
                Facing = ThreatDir; } Want *= bVig ? EatMult : GaitEat[Gait]; 다음 Perception 의 FOV = bVig ? 360 : 120.
                Perception(ThreatDir 갱신) 뒤: if (bVig && Fov >= 360 && !ThreatDir.IsZero()) Facing = ThreatDir;
        스텝 뒤 훅(replay_v2): `self.vigilant`, `self.gaze`(스텝 뒤 heading, 리스폰 전), `self.vel`(적용 속도).
        리스폰은 이 훅을 바꾸지 않는다(죽은 슬롯의 마지막 프레임이 그 개체의 값이다).
        """
        vig = a_vig > self._vg["threshold"]
        if win is not None:
            vig = vig & win
        v = np.where(vig[:, None], 0.0, v)
        if self._sp is not None:
            self.gait = np.where(vig, GAIT_STOP, self.gait).astype(np.int8)
        self.vel = v
        self.vigilant = vig
        return v

    def _threat_flee_term(self) -> np.ndarray:
        """10절 #18 조향 변형 항 (N,2). `step` 1) 에서 threat_flee > 0 일 때만 `steer` 의 정규화 전 합에 더한다.

        결정 관측(이전 스텝 끝 8b)에서 포식자가 안 보인 개체: threat_flee · flee_weight · threat_recency · (−ThreatDir).
        보인 개체는 0 이다(v1 도주 항 `d_pred < flee_dist·see_r` 이 맡는다). 위협을 본 적 없으면 ThreatDir = 0 이라 0.
        threat_recency 가 감쇠하므로 놓친 직후에 크고(최대 flee_weight 배) 시간이 지나면 줄어든다. 구간과 무관하게
        안 보인 모든 개체에 걸린다(threat_recency < θ 인 평시 개체에도 θ·flee_weight 이하로 남는다).
        계약 밖의 시험 항이다(#18 '넣지 않고 시작한다'). Gate E2b 의 '계속 뛰기' 변형 팔에만 켜고, 크게 이기면 조향
        계약 변경안에 올린다. C++ 꼴: if (PredCount == 0) V += ThreatFlee * FleeWeight * Recency * (-ThreatDir);
        """
        unseen = self._g["pred_count"] == 0
        k = self._vg["threat_flee"] * self.cfg.flee_weight
        return np.where(unseen[:, None], (-k) * self.threat[:, None] * self.threat_dir, 0.0)

    def _face_threat(self) -> None:
        """경계한 개체의 heading ← ThreatDir (0 이면 유지), 시선 훅 갱신. `step` 1e) 와 8c) (`_vigil_step` docstring)."""
        face = self.vigilant & (self.threat_dir != 0.0).any(1)
        self.head[face] = self.threat_dir[face]
        self.gaze = self.head.copy()

    def _look_back(self) -> None:
        """v2.2r L 반사 돌아보기 (수정 제안서 3.1 (나), R2). `step` 1f) — 이동·heading 갱신(1d)과 경계 돌아보기(1e) 뒤.

        조건: 결정 때 창 안(`self.window`, `step` 0) & 이번 스텝의 실제 보행이 정지(`self.gait`, 경계 포함) & ThreatDir ≠ 0.
        그러면 heading ← ThreatDir(마지막 위협 방향, 단위벡터). 섭식·대사·시야는 정지 그대로다(섭식 gait_eat[정지],
        대사 c_rest, 다음 관측 기본 FOV). 그래서 이득은 돌아보기 하나 — 다음 관측(8)의 120° 시야가 놓친 포식자 쪽을
        향한다. 멈출지는 RL 이 speed 로 고른다(창 밖에서 멈춰도 반사가 없고, 상수 정책은 창 안에서만 멈출 수 없다).
        정지 개체는 v = 0 이라 1d 가 heading 을 바꾸지 않으므로 이 반사가 스텝 끝 heading 이다. 포식자는 heading 을
        보지 않는다(v1 그대로).
        C++ 꼴 (SteerV2, 이동 뒤): if (bWindow && Gait == Stop && !ThreatDir.IsZero()) Facing = ThreatDir;
               bWindow = (PredCount == 0 && Recency > Theta)  — 결정 관측 기준.
        스텝 뒤 훅(replay_v2): `self.looked`(반사가 돈 개체), `self.gaze`(스텝 뒤 heading).
        """
        face = self.window & (self.gait == GAIT_STOP) & (self.threat_dir != 0.0).any(1)
        self.head[face] = self.threat_dir[face]
        self.looked = face
        self.gaze = self.head.copy()

    def _gait_step(self, v: np.ndarray, a_speed: np.ndarray) -> np.ndarray:
        """v2.1 보행 (계획서 4.3·4.4). `step` 1) 에서 v1 조향 속도 `v`(크기 herb_speed 또는 0)의 크기만 바꾼다.

        한 스텝 순서 — C++ 로 옮길 때 이 순서를 지킨다. 상태가 없다(이전 스텝의 보행을 읽지 않는다):
          1a) 명령 보행 cmd = [a ≥ t_walk] + [a ≥ t_run] (0 정지, 1 걷기, 2 뛰기). a 는 sigmoid 뒤 [0,1] 값이고
              문턱은 고정값이다(최소 유지 시간 K 없음, #3)
          1b) 실제 보행 g = cmd. 단 조향 합의 방향이 없으면(|v| ≤ EPS, v1 의 '안 움직임' 판정과 같다) g = 정지.
              갈 방향이 없는 '걷기'는 제자리에 서 있는 것이므로 섭식·대사도 정지로 친다
          1c) v ← v × gait_speed[g]. 조향 방향 계산(steering.py)은 그대로다. 뛰기 1.0 이면 v1 속도와 비트 단위로 같다
          1d) (step) pos ← clip(pos + v, 0, size), |v| > EPS 면 heading ← v 방향, 아니면 유지 — v1 과 같은 줄이다.
              정지는 v = 0 이라 heading 을 유지한다. 벽에 막혀 실제 이동이 짧아도 대사는 보행 상태의 속력으로 낸다
              (clamp 전 v 로 heading 을 정하는 v1 과 같은 기준)
          2)  (step) 포식자 — v1 그대로
          3a) (step) 대사 drain = energy_drain × drain_mult[g], drain_mult = c_rest + c_move·gait_speed²
              (계획서 drain = energy_drain·(c_rest + c_move·(v/herb_speed)²) 에서 v/herb_speed = gait_speed[g])
          3b) (step) 섭식 want ← clip((max − e_drained)/fepu, 0, food_eat_rate) × gait_eat[g] (`_eat`), 나머지 v1
          3c) (step) 에너지 보상: net_energy_reward 면 e_new − e_prev, 아니면 v1 획득량 e_new − e_drained.
              번식 리셋(4)·리스폰(8)은 그 뒤라 순변화에 들어가지 않는다
        C++ 꼴 (V = v1 조향 합을 정규화해 HerbSpeed 를 곱한 값, 지금 SteeringProcessor 의 Velocity):
                Cmd = (A >= TWalk) + (A >= TRun); G = (V.SizeSquared() > EPS * EPS) ? Cmd : Stop;
                Velocity = V * GaitSpeed[G]; Drain = EnergyDrain * DrainMult[G]; Want *= GaitEat[G].
        스텝 뒤 훅(replay_v2): `self.gait` 실제 보행, `self.gait_cmd` 명령 보행, `self.vel` 적용 속도(벽 clamp 전).
        """
        sp = self._sp
        t_walk, t_run = sp["thresholds"]
        cmd = (a_speed >= t_walk).view(np.int8) + (a_speed >= t_run).view(np.int8)
        # |v| > EPS ⇔ v·v > EPS². steer 의 v 는 0 이거나 크기 herb_speed 라 경계 근처 값이 없다. 정지 = 0 이라 곱으로 고른다
        g = cmd * ((v * v).sum(1) > EPS * EPS)
        v = v * sp["speed"][g][:, None]
        self.gait, self.gait_cmd, self.vel = g, cmd, v
        return v

    def _rep_decision_obs(self) -> dict:
        """`repertoire.arbitrate` 의 결정 때 입력 (repertoire docstring A '결정 때 관측(이전 스텝 끝 기하)'): 지금 기하
        `self._g`(리스폰 관측 포함)의 포식자 수·가장 가까운 거리·접근 속력·사건 비교 시야 값·은신처와 지금 에너지(max_energy
        비율)·어둠. `_rep_step`(실제 결정)과 `rep_peek`(미리 보기)가 같은 이 함수를 써서 두 입력이 늘 같다."""
        g = self._g
        return dict(pred_count=g["pred_count"], d_pred_min=g["d_pred_min"], pred_approach=g["pred_approach"],
                    pred_count_ev=g["pred_count_ev"], d_pred_min_ev=g["d_pred_min_ev"],
                    pred_approach_ev=g["pred_approach_ev"],
                    energy=np.clip(self.energy / self.cfg.max_energy, 0.0, 1.0), dark=self.dark,
                    in_cover=g["in_cover"], cover_k=g["cover_k"])

    def rep_peek(self) -> dict:
        """다음 `step` 의 `arbitrate` 가 요청을 읽는지 미리 본다 (R1 명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 2절 '결정').
        순수 함수다 — 행동 상태(RepState)를 복사해 같은 결정 때 입력(`_rep_decision_obs`)으로 `arbitrate` 를 돌려 보고 버린다.
        세계 상태와 난수를 건드리지 않으므로 부르든 부르지 않든 궤적이 비트 단위로 같다(tests/test_rep_policy_v3.py).

        반환 (모두 (N,) 사본):
          - reads: 요청을 읽는 개체 = 결정 시점((lock_left ≤ 0 또는 사건 fire) & 기상 중 아님 & 이번 스텝에 깨지 않음) 또는
            기상 결정(이번 스텝에 깨고 wake_ev 가 있음). `arbitrate` 반환의 decide 와 같은 값이다
          - wake_decide: 기상 결정인 개체(기상 결정의 SLEEP 요청은 wake_target 으로 바뀌므로 마스크가 SLEEP 을 막는다)
          - behavior: 지금 행동(int64, 결정 전 — 관측 obs_extra 의 행동 one-hot 과 같은 값)
        `decide` 는 요청 값과 무관하므로(잠금·사건·기상만 본다) 미리 보기의 요청은 지금 행동으로 둔다.
        """
        if self._rp is None:
            raise ValueError("rep_peek 은 repertoire 를 켠 세계에만 있다")
        rs = self._rs
        cp = object.__new__(rep.RepState)
        cp.__dict__.update({k: np.array(v, copy=True) for k, v in vars(rs).items()})
        woke = rs.waking & (rs.wake_left <= 0)          # arbitrate d. 의 woke 는 a~c 가 바꾸지 않는 칸만 본다
        res = rep.arbitrate(cp, self._rp, rs.behavior.astype(np.int64), self._rep_decision_obs())
        reads = np.asarray(res["decide"], dtype=bool).copy()
        return dict(reads=reads, wake_decide=reads & woke, behavior=rs.behavior.astype(np.int64))

    def _rep_step(self, a: np.ndarray) -> tuple[np.ndarray, dict]:
        """v3 행동 실행기 한 스텝 (`step` 0r·1r, 순서는 env_v2/repertoire.py docstring A·B). 반환: (적용 속도, 제어 결과).

        요청 = a[:, 0] 이고 0..4 의 정수 행동 번호여야 한다. 정수가 아니면 멈춘다 — 연속 정책(random [0, 1)·학습 정책의
        sigmoid (0, 1))을 내림하면 조용히 늘 GRAZE 가 되기 때문이다(random 은 `env_v2/rollout.adapt_spec` 이 정수 행동을 뽑는다).
        결정 때 입력은 이전 스텝 끝 기하 `self._g`(포식자 수·가장 가까운 거리·접근 속력·사건 비교 시야 값·은신처)와 결정 때
        에너지·어둠이다. GRAZE 의 '먹이 충분'은 결정 때 위치 셀의 먹이(섭식 전) ≥ graze_eat_min 이다. HIDE 는 고른 은신처의
        중심 쪽으로 간다(가장자리까지의 가장 가까운 점과 같은 방향).
        스텝 뒤 훅: `self.gait`(실제 보행, gait_cmd 도 같은 값 — 명령 보행이 없다), `self.vel`(적용 속도).
        """
        rp, rs, g, cfg = self._rp, self._rs, self._g, self.cfg
        req = a[:, 0]
        if (not np.all(np.isfinite(req)) or req.min() < 0 or req.max() >= rep.N_BEHAVIORS
                or not np.all(req == np.floor(req))):
            bad = req[~np.isfinite(req) | (req != np.floor(req))]
            raise ValueError(f"행동 'behavior' 는 0..{rep.N_BEHAVIORS - 1} 의 정수 행동 번호여야 한다(내림하지 않는다 — "
                             f"연속 정책 출력은 이 세계에 쓸 수 없다). 받은 범위: [{req.min()}, {req.max()}]"
                             + (f", 정수가 아닌 값 예: {bad[:3].tolist()}" if len(bad) else ""))
        prev = rs.behavior.copy()
        res = rep.arbitrate(rs, rp, req.astype(np.int64), self._rep_decision_obs())
        ix, iy = self._cell_index(self.pos)
        to_target = np.zeros((self.N, 2))
        m = (rs.behavior == rep.HIDE) & ~rs.arrived & (rs.hide_target >= 0)
        if m.any():
            to_target[m] = normalize(self.cov_c[rs.hide_target[m]] - self.pos[m])
        inp = dict(food_grad=g["food_grad"], to_centroid=g["to_centroid"], separation=g["separation"],
                   away_from_pred=g["away_from_pred"], to_target=to_target, pred_count=g["pred_count"],
                   food_ok=self.food[iy, ix] >= rp["graze_eat_min"], in_cover=g["in_cover"], dark=self.dark)
        out = rep.control(rs, rp, inp, cfg, self._sp)
        self.gait, self.gait_cmd, self.vel = out["gait"], out["gait"].copy(), out["vel"]
        self._rep_eat, self._rep_drain = out["eat"], out["drain"]
        self._rep_see_last = self._rep_see                  # 결정 관측(self._g)을 만든 배수 → 다음 관측의 '직전' 배수
        self._rep_see, self._rep_still = out["see"], out["still"]
        # M6 행동별 은신 배수(은신처 안일 때): 웅크린 HIDE, GRAZE, SLEEP, 그 밖 (repertoire.cover_mult)
        self._rep_cover = rep.cover_mult(rp, rs.behavior, out["crouch"])
        out.update(res)
        out["prev"] = prev
        return out["vel"], out

    def _step_predators(self) -> np.ndarray:
        """포식자 2종 (§4.2). 은신처 안 초식은 거리가 `cover_hide_mult` 배로 보인다."""
        cfg = self.cfg
        if self.M == 0:
            return np.zeros(self.N, dtype=bool)

        ar = np.arange(self.M)
        dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]      # (M,N)
        dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        inv = 1.0 / np.maximum(dist, EPS)
        # 이번 스텝 이동 후 위치 기준. self._g는 이동 전 기하라 여기서 다시 판정한다.
        hide = np.where(self._in_cover(self.pos), cfg.cover_hide_mult, 1.0)[None, :]
        perceived = dist * hide
        self.pred_cd = np.maximum(self.pred_cd - 1, 0)
        hunting = self.pred_cd == 0
        if self._ps is not None:        # v2.4s: 자는 포식자는 사냥하지 않는다(쿨다운은 그대로 준다)
            hunting = hunting & ~self.pred_asleep
        vis = (
            (perceived <= cfg.pred_view_r)
            & (
                (dx * self.pred_head[:, 0:1] + dy * self.pred_head[:, 1:2]) * inv
                >= cfg.pred_fov_cos
            )
            & hunting[:, None]
        )

        # 추적: 시야 내 최근접(체감 거리 기준)
        masked = np.where(vis, perceived, np.inf)
        j = masked.argmin(1)
        has_target = np.isfinite(masked[ar, j])
        turn = self.rng.uniform(-cfg.pred_wander_turn, cfg.pred_wander_turn, self.M)
        c, s = np.cos(turn), np.sin(turn)
        wander = np.stack(
            [
                self.pred_head[:, 0] * c - self.pred_head[:, 1] * s,
                self.pred_head[:, 0] * s + self.pred_head[:, 1] * c,
            ],
            1,
        )
        chase = np.stack([dx[ar, j], dy[ar, j]], 1) * inv[ar, j][:, None]
        move = np.where(has_target[:, None], chase, wander)
        if self._ps is None:
            self.pred_pos = self.pred_pos + move * self.pred_speed[:, None]
        else:                           # v2.4s: 자는 포식자는 멈추고 방향을 유지한다. 깨어 있는 주행성은 박명 감속
            move = np.where(self.pred_asleep[:, None], self.pred_head, move)
            self.pred_pos = self.pred_pos + move * (self.pred_speed * self._pred_speed_mult)[:, None]
            self._ps_asleep_sum += float(self.pred_asleep.mean()) if self.M else 0.0
            self._ps_steps += 1
        # 벽에서 반사 (§4.2 토러스 끄기)
        for axis in (0, 1):
            out_of = (self.pred_pos[:, axis] < 0.0) | (self.pred_pos[:, axis] > self.size)
            move[out_of, axis] *= -1.0
        self.pred_pos = np.clip(self.pred_pos, 0.0, self.size)
        self.pred_head = normalize(move)

        # 포획: 근접형은 결정적, 원거리형은 확률적 (§4.2). 포식자당 한 스텝 한 마리.
        hit = (perceived <= self.pred_catch_r[:, None]) & hunting[:, None]
        if self.pred_ranged.any():
            roll = self.rng.random((self.M, self.N)) < cfg.pred_ranged_catch_p
            hit &= np.where(self.pred_ranged[:, None], roll, True)
        hit_d = np.where(hit, perceived, np.inf)
        k = hit_d.argmin(1)
        got = np.isfinite(hit_d[ar, k])
        caught = np.zeros(self.N, dtype=bool)
        caught[k[got]] = True
        self.pred_cd[got] = int(cfg.pred_eat_cd)
        return caught

    def _step_predators_v3(self) -> np.ndarray:
        """v3 포식자·위협 스텝 (repertoire·threats 중 하나라도 켠 세계, 명세 3절). `_step_predators` 와 같은 순서다:
        체감 거리 → 쿨다운 → 표적(시야 안 최근접 체감 거리) → 이동 → 벽 반사 → 포획(이동 전 거리, v1 그대로).

        - 체감 거리 (repertoire): 표적 선택 = 실거리 × max(은신 배수, still 이면 c_still)(M1·M6), 포획 = 실거리 × 은신 배수.
          은신 배수 = 은신처 안이면 행동별 값(웅크린 HIDE cover_mult_crouch, GRAZE cover_mult_graze, SLEEP cover_mult_sleep,
          그 밖 cover_mult_other — `repertoire.cover_mult`), 밖이면 1.
          repertoire 를 끈 세계는 v1 그대로 은신처 안 cover_hide_mult 를 둘 다에 쓴다.
        - 잠행형 (threats, M3): 배회 중 표적이 있고 체감 거리 > stalk_dist 면 stalk_speed 로 잠행, ≤ stalk_dist 면 돌진을
          시작한다(pounce_speed 로 pounce_steps 번 이동, 표적이 안 보이면 곧장). 돌진 이동을 다 쓴 다음 스텝이 마지막 포획
          판정이고(느리게 곧장), 놓치면 exhaust_steps 동안 탈진(exhaust_speed 로 배회, 사냥 안 함). 잡으면 배회로 돌아간다.
          자는 잠행형은 처음 상태로 돌아간다. 밤잠·박명 감속은 추격형과 같다.
        - 플레이어 (threats): 맵 전체를 본다(시야 반경·각 없음, 체감 거리는 같다 — 사람 플레이어는 화면의 모든 개체를 본다.
          그래서 정지·웅크림은 플레이어의 표적 순위만 바꾸고 표적에서 벗어나게 하지는 못한다. 명세의 '가장 가까운 무리'는
          '체감 거리가 가장 가까운 개체'로 둔다. 결정 기록은 results/v3/r0/PREREG.md 변경 기록). 배회(player_speeds[0], 선회는
          자기 스트림 part 3) · 잠행(player_speeds[1], 가장 가까운 개체 쪽, 체감 거리 ≤ player_charge_dist 면 돌진 시작) · 돌진
          (player_speeds[2] 로 player_charge_steps 번, 마지막 판정 뒤 휴식) · 휴식(멈춤, 사냥 안 함, player_rest_steps).
          배회·잠행 모드 길이가 끝나거나 휴식이 끝나면 모드를 새로 고른다(`_player_new_mode`). 포획 뒤 쿨다운 player_cooldown.
          밤에 자지 않는다.
        - v1 스트림: 배회 선회 M_base 개, v1 원거리형 배치에 원거리형이 있으면 원거리 판정 (M_base, N) 개 — v2.4s 와 같은 모양
          (플레이어 몫은 threats 스트림, 잠행형이 덮은 원거리형의 판정은 쓰지 않는다).
        스텝 뒤 훅: `self.pred_vel`(이번 스텝 실제 이동, 관측 pred_approach).
        """
        cfg, th, rp = self.cfg, self._th, self._rp
        M, Mb, N = self.M, self.M_base, self.N
        if M == 0:
            return np.zeros(N, dtype=bool)
        ar = np.arange(M)
        old = self.pred_pos.copy()
        dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]      # (M,N)
        dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        inv = 1.0 / np.maximum(dist, EPS)
        in_cov = self._in_cover(self.pos)
        if rp is not None:
            cov = np.where(in_cov, self._rep_cover, 1.0)
            det = np.maximum(cov, np.where(self._rep_still, rp["c_still"], 1.0))
        else:
            cov = det = np.where(in_cov, cfg.cover_hide_mult, 1.0)
        perceived = dist * det[None, :]
        catch_d = dist * cov[None, :]
        self.pred_cd = np.maximum(self.pred_cd - 1, 0)
        hunting = self.pred_cd == 0
        if self._ps is not None:
            hunting = hunting & ~self.pred_asleep
        ts = None
        if th is not None:
            stalker = self.pred_type == PT_STALKER
            if self._ps is not None:
                zz = stalker & self.pred_asleep
                self.stalk_state[zz] = ST_ROAM
                self.stalk_left[zz] = 0
            exh0 = stalker & (self.stalk_state == ST_EXHAUST)
            rest0 = self.pred_is_player & (self.player_mode == PM_REST)
            hunting = hunting & ~exh0 & ~rest0
        vis = (perceived <= cfg.pred_view_r) & (
            (dx * self.pred_head[:, 0:1] + dy * self.pred_head[:, 1:2]) * inv >= cfg.pred_fov_cos)
        if th is not None and M > Mb:
            vis[self.pred_is_player] = True
        vis &= hunting[:, None]
        masked = np.where(vis, perceived, np.inf)
        j = masked.argmin(1)
        d_t = masked[ar, j]
        has_target = np.isfinite(d_t)
        turn = self.rng.uniform(-cfg.pred_wander_turn, cfg.pred_wander_turn, Mb)
        if M > Mb:
            turn = np.concatenate([turn, self.feature_rng("threats", 3).uniform(
                -cfg.pred_wander_turn, cfg.pred_wander_turn, M - Mb)])
        c, s = np.cos(turn), np.sin(turn)
        wander = np.stack([self.pred_head[:, 0] * c - self.pred_head[:, 1] * s,
                           self.pred_head[:, 0] * s + self.pred_head[:, 1] * c], 1)
        chase = np.stack([dx[ar, j], dy[ar, j]], 1) * inv[ar, j][:, None]
        move = np.where(has_target[:, None], chase, wander)
        speed = self.pred_speed.copy()
        if th is not None:
            move, speed, ts = self._threat_motion(move, speed, wander, has_target, d_t, exh0, rest0)
        if self._ps is not None:
            move = np.where(self.pred_asleep[:, None], self.pred_head, move)
            speed = speed * self._pred_speed_mult
            self._ps_asleep_sum += float(self.pred_asleep[:Mb].mean()) if Mb else 0.0
            self._ps_steps += 1
        self.pred_pos = self.pred_pos + move * speed[:, None]
        for axis in (0, 1):
            out_of = (self.pred_pos[:, axis] < 0.0) | (self.pred_pos[:, axis] > self.size)
            move[out_of, axis] *= -1.0
        self.pred_pos = np.clip(self.pred_pos, 0.0, self.size)
        self.pred_head = normalize(move)
        self.pred_vel = self.pred_pos - old

        hit = (catch_d <= self.pred_catch_r[:, None]) & hunting[:, None]
        if self._pred_ranged_v1[:Mb].any():
            roll = self.rng.random((Mb, N)) < cfg.pred_ranged_catch_p
            if M > Mb:
                roll = np.vstack([roll, np.ones((M - Mb, N), dtype=bool)])
            hit &= np.where(self.pred_ranged[:, None], roll, True)
        hit_d = np.where(hit, catch_d, np.inf)
        k = hit_d.argmin(1)
        got = np.isfinite(hit_d[ar, k])
        caught = np.zeros(N, dtype=bool)
        caught[k[got]] = True
        if th is None:
            self.pred_cd[got] = int(cfg.pred_eat_cd)
        else:
            self.pred_cd[got] = np.where(self.pred_is_player[got], th["player_cooldown"], int(cfg.pred_eat_cd))
            self._threat_after(got, ts)
        return caught

    def _threat_motion(self, move, speed, wander, has_target, d_t, exh0, rest0):
        """잠행형·플레이어의 이번 스텝 이동 방향·속력과 상태 시작(돌진·플레이어 돌진). `_step_predators_v3` docstring."""
        th, hs = self._th, self.cfg.herb_speed
        stalker = self.pred_type == PT_STALKER
        st, left = self.stalk_state, self.stalk_left
        roam = stalker & (st == ST_ROAM)
        start = roam & has_target & (d_t <= th["stalk_dist"])
        st[start] = ST_POUNCE
        left[start] = th["pounce_steps"]
        self._th_pounce[0] += int(np.count_nonzero(start))
        stalking = roam & has_target & ~start
        pounce = stalker & (st == ST_POUNCE)
        final = pounce & (left <= 0)
        dash = pounce & ~final
        speed = np.where(stalking, th["stalk_speed"] * hs, speed)
        speed = np.where(dash, th["pounce_speed"] * hs, speed)
        speed = np.where(exh0 | final, th["exhaust_speed"] * hs, speed)
        move = np.where(((dash & ~has_target) | final)[:, None], self.pred_head, move)
        ps = th["player_speeds"]
        for i in np.flatnonzero(self.pred_is_player):
            if self.player_mode[i] == PM_STALK and has_target[i] and d_t[i] <= th["player_charge_dist"]:
                self.player_mode[i] = PM_CHARGE
                self.player_left[i] = th["player_charge_steps"]
                self._th_charge += 1
            mode = self.player_mode[i]
            if mode == PM_WANDER:
                speed[i], move[i] = ps[0] * hs, wander[i]
            elif mode == PM_STALK:
                speed[i] = ps[1] * hs                   # 표적 쪽(없으면 배회)
            elif mode == PM_CHARGE and self.player_left[i] > 0:
                speed[i] = ps[2] * hs
                if not has_target[i]:
                    move[i] = self.pred_head[i]
            else:                                       # 휴식, 또는 돌진 뒤 마지막 판정 스텝
                speed[i], move[i] = 0.0, self.pred_head[i]
        return move, speed, dict(final=final, dash=dash, exh0=exh0, rest0=rest0)

    def _threat_after(self, got: np.ndarray, ts: dict) -> None:
        """포획 뒤 잠행형·플레이어 상태 갱신과 유형별 포획 수 (`_step_predators_v3` docstring)."""
        th = self._th
        stalker = self.pred_type == PT_STALKER
        st, left = self.stalk_state, self.stalk_left
        hitp = stalker & (st == ST_POUNCE) & got
        self._th_pounce[1] += int(np.count_nonzero(hitp))
        st[hitp] = ST_ROAM
        left[hitp] = 0
        fin = ts["final"] & ~got
        st[fin] = ST_EXHAUST if th["exhaust_steps"] > 0 else ST_ROAM
        left[fin] = th["exhaust_steps"]
        cont = ts["dash"] & ~got
        left[cont] -= 1
        e = ts["exh0"]
        left[e] -= 1
        back = e & (left <= 0)
        st[back] = ST_ROAM
        left[back] = 0
        kind = np.where(self.pred_is_player, 3, np.where(stalker, 2, np.where(self.pred_ranged, 1, 0)))
        self._th_catch += np.bincount(kind[got], minlength=4)
        for i in np.flatnonzero(self.pred_is_player):
            mode = self.player_mode[i]
            if mode == PM_CHARGE:
                if got[i] or self.player_left[i] <= 0:
                    self.player_mode[i] = PM_REST
                    self.player_left[i] = th["player_rest_steps"]
                    if th["player_rest_steps"] <= 0:
                        self._player_new_mode(i)
                else:
                    self.player_left[i] -= 1
            else:                                       # 배회·잠행·휴식: 남은 길이를 줄이고 끝나면 새 모드
                self.player_left[i] -= 1
                if self.player_left[i] <= 0:
                    self._player_new_mode(i)

    def _eat(self, e_drained: np.ndarray, mult: np.ndarray | None = None) -> np.ndarray:
        """셀당 총 수요를 잔량에 비례 배분한다. 개체별 루프 없음 (§1.1).

        수요는 **흡수 가능량**으로 제한한다: 배부른 개체가 먹이를 계속 퍼가면 맵 전체가
        벗겨져서(측정: food가 0.02로 수렴) 먹이 탐색이 무의미해진다. 이렇게 두면 총
        소비량이 총 대사 수요를 따라가고 패치가 유지된다.

        `mult` (N,) 는 v2.1 보행 섭식 배수다(speed). 흡수 가능량 상한까지 자른 want 에 곱한 뒤 셀 수요를 합친다.
        뛰는 개체(0)는 수요가 없어 같은 셀 개체의 몫을 줄이지 않는다. None 이면 v1 과 같다.
        """
        cfg = self.cfg
        want = np.clip(
            (cfg.max_energy - e_drained) / cfg.food_energy_per_unit, 0.0, cfg.food_eat_rate
        )
        if mult is not None:
            want = want * mult
        ix, iy = self._cell_index(self.pos)
        flat = iy * self.gw + ix
        cells = self.gw * self.gw
        demand = np.bincount(flat, weights=want, minlength=cells)
        taken = np.minimum(demand, self.food.reshape(-1))
        frac = np.divide(taken, demand, out=np.zeros(cells), where=demand > 0)
        self.food -= taken.reshape(self.gw, self.gw)
        if self._fv is not None:
            self._fv_taken = taken          # v2.0b 훼손이 셀별 섭취량을 쓴다 (_food_v_step)
        return want * frac[flat]

    def _food_v_step(self) -> None:
        """v2.0b 먹이 2층의 한 스텝 (계획서 4.9.1). `step` 7) 에서 v1 재생 대신 부른다.

        셀마다 F = self.food, V = self.food_v(식생 용량), cap0 = self.food_cap, r = self.regen_field
        (은신처 0.3배 포함, v1 그대로). 한 스텝의 순서 — C++ 로 옮길 때 이 순서를 지킨다:

          3)  섭식 (`_eat`): F ← F − taken. taken ≤ F 라 F ≥ 0.
              4)~6) 번식·사망·피식 EMA 는 F·V 를 읽지 않으므로 훼손을 3) 직후에 해도 결과가 같다.
          7a) 훼손 (taken > 0 인 셀만): V ← V − α·taken·(1 − F/V). F 는 섭취 직후 값, V 는 훼손 전 값.
              taken > 0 이면 섭취 전 F ≥ taken > 0 이고 V ≥ 섭취 전 F 라 V > 0 이다 — 0 나눗셈이 없다.
          7b) 하한: V ← max(V, floor·cap0).
          7c) F ← min(F, V). α ≤ 1 이면 수학적으로는 바뀌지 않지만 반올림·α > 1 대비로 둔다.
          7d) 재생 (모든 셀): F ← F + r·(V − F), F ← min(F, V). v1 식(목표·상한 cap0)의 cap0 를 V 로
              바꾼 것이다. v1 은 clip(F, 0, cap0) 이지만 여기서는 F ≥ 0, V ≥ F 라 r·(V − F) ≥ 0 이고
              하한 0 이 저절로 지켜져 상한만 자른다(결과가 같다).
          7e) 휴식 회복 (모든 셀): V ← V + ρ·(cap0 − V), ρ = 1 − 2^(−1/h). 섭식이 없으면 cap0 − V 가
              h 스텝마다 절반이 된다. V 가 cap0 쪽으로만 움직이므로 F ≤ V ≤ cap0, V ≥ floor·cap0 가 유지된다.

        taken 은 고정 스텝 하나(1스텝 = 0.133s) 동안 그 셀에 들어간 모든 개체 섭취의 합이고(`_eat` 의 셀별 합),
        7a~7e 는 모든 섭식이 끝난 뒤 셀마다 한 번 계산한다. (1 − F/V) 가 비선형이라 개체마다·프레임마다 V 를
        바로 깎으면 같은 섭취량에서도 훼손이 작아진다(막 자란 셀을 8번에 나눠 먹으면 약 −45%). C++ 는
        ConsumeFood 를 셀별 버퍼에 누적했다가 같은 고정 간격으로 한 번 갱신한다. r·ρ 는 스텝당 값이라 간격 dt 를
        바꾸면 r' = 1 − (1 − r)^(dt/0.133s), ρ' = 1 − 2^(−dt/(h·0.133s)) 로 다시 환산하고, α 는 분할에 불변이
        아니므로 다시 보정한다.

        스텝 끝 불변식: 0 ≤ F ≤ V ≤ cap0, floor·cap0 ≤ V. cap0 = 0 셀은 F = V = 0 이다.
        taken > 0 가드는 최적화이면서 필수다. taken = 0 이고 V > 0 인 셀에서 7a~7c 는 항등이지만, cap0 = 0 셀
        (V = F = 0)을 조밀하게 계산하면 0·(1 − 0/0) = NaN 이 되어 F 와 관측 0 의 food_blur 누적합으로 퍼진다.
        그래서 먹힌 셀(많아야 N 개)만 계산한다(C++ 도 `if (Taken > 0)`). 가드를 단 조밀 계산과 비트 단위로 같다.
        α = 0 이고 V = cap0 로 시작하면 V 가 비트 단위로 cap0 에 머물러 v2.0(= v1) 세계와 같다
        (둘 다 tests/test_food_v2.py).
        """
        fv = self._fv
        F, V = self.food.reshape(-1), self.food_v.reshape(-1)     # 연속 배열의 뷰 — 제자리 갱신
        taken = self._fv_taken
        k = (taken > 0.0).nonzero()[0]      # taken ≥ 0. float 배열의 flatnonzero 보다 몇 배 빠르다
        if k.size:
            tk, f, v = taken[k], F[k], V[k]
            v = np.maximum(v - fv["alpha"] * tk * (1.0 - f / v), self._fv_floor.reshape(-1)[k])
            V[k] = v
            F[k] = np.minimum(f, v)
            self._fv_eaten.reshape(-1)[k] += tk
            self._fv_last_eat.reshape(-1)[k] = self.t + 1     # 이 스텝이 끝난 뒤의 self.t
        # 7d·7e 는 임시 배열 하나를 같이 쓴다 (r·(V − F) 와 (V − F)·r 은 같은 값이다)
        d = np.subtract(self.food_v, self.food)
        d *= self.regen_field
        self.food += d
        np.minimum(self.food, self.food_v, out=self.food)
        np.subtract(self.food_cap, self.food_v, out=d)
        d *= self.food_v_rho
        self.food_v += d

    def _respawn(self, dead: np.ndarray) -> None:
        """§4.3 — 죽은 슬롯에 랜덤 위치로 리스폰. 개체군 동역학은 넣지 않는다."""
        r, k = self.rng, len(dead)
        self.pos[dead] = r.uniform(0.0, self.size, (k, 2))
        ang = r.uniform(0.0, 2 * np.pi, k)
        self.head[dead] = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy[dead] = self.cfg.init_energy
        self.repro_cd[dead] = 0
        if self._vg is not None:        # v2.2 개체별 상태 초기화 (계획서 4.2·4.4). 난수를 쓰지 않는다
            self.threat[dead] = 0.0
            self.threat_dir[dead] = 0.0
            self._wide[dead] = False
            self._near[dead] = False            # 통계 전용 기준 상태도 새 개체로 (`_perceive`)
            self._tr_truth[dead] = 0.0
        if self._dn is not None and self._dn["start_induce"] > 0.0:
            # v2.4 시작 상태 유도(탐침 대응, 0 이면 없음): daynight 스트림 part 3 에서 리스폰 개체마다 2개(u, 에너지)를
            # 늘 뽑고(소비가 결과와 무관하다) u < start_induce 면 에너지를 U[0.2, 0.5]·max_energy 로 둔다. 낮 고정 세계는
            # reset 유도처럼 바꾸지 않는다(낮 고정 세계 = v2.1 동역학). v1 스트림 호출(위)은 그대로다
            g = self.feature_rng("daynight", 3)
            u = g.random(k)
            e = g.uniform(INDUCE_ENERGY[0], INDUCE_ENERGY[1], k) * self.cfg.max_energy
            if not self.day_fixed:
                self.energy[dead] = np.where(u < self._dn["start_induce"], e, self.energy[dead])
        if self._rp is not None:
            # v3: 새 개체는 GRAZE 진입 상태(잠금 lock_graze), 사건 기준값은 리스폰 때 값(에너지·어둠), 세대 + 1 로 사건 결정
            # 지연을 새로 받는다(C++ AgentKey 가 리스폰마다 새 값인 것과 같다). 난수를 쓰지 않는다.
            # 스텝 뒤 훅(behavior 등)은 바꾸지 않는다(`_rep_export`). 깜빡임 통계는 이전 개체와 잇지 않는다
            self._rep_gen[dead] += 1
            self._rs.reset_slots(dead, self._rp, self.energy[dead] / self.cfg.max_energy, self.dark, self.seed,
                                 self._rep_gen[dead])
            self._rep_see[dead] = self._rp["graze_head_down"]
            self._rep_see_last[dead] = self._rp["graze_head_down"]
            self._rep_before[dead] = -1
            self._rep_last_sw[dead] = -(10 ** 9)

    # ------------------------------------------------------------------ #
    # 통계 (§7.2)
    # ------------------------------------------------------------------ #

    def _reset_stats(self) -> None:
        self._rew_total = 0.0
        self._repro_total = 0
        self._pred_deaths = 0
        self._starve_deaths = 0   # §7.2 열은 아니고 경제 보정용 진단 카운터
        self._life_sum = 0
        self._life_count = 0
        self._life_cur = np.zeros(self.N, dtype=np.int64)
        # repertoire 세계의 v1 행동 열 합은 0 자리(행동이 'behavior' 한 열이라 v1 stats 의 조향 열이 없다)
        self._act_sum = np.zeros(ACT_DIM if self._rp is not None else self.act_dim)
        self._flee_sq = 0.0
        self._cover_steps = 0
        self._agent_steps = 0
        self._a_pred = np.zeros(3)   # cohesion, flee_dist, cover — 포식자 보일 때
        self._n_pred = 0
        self._a_nopred = np.zeros(3)
        self._n_nopred = 0
        self._f_hungry, self._n_hungry = 0.0, 0
        self._f_full, self._n_full = 0.0, 0
        if self._sp is not None:     # v2.1 보행 지표 (gait_stats). 모두 개체-스텝 수다
            # 개체-스텝 히스토그램 [경계 2, 실제 보행 3, 명령 보행 3, 포식자 거리 구간 4, 배부름 2]. 거리 구간은
            # [안 보임, d<0.25, 0.25≤d<0.5, d≥0.5] (d = d_pred/see_r), 배부름은 [energy<0.5, ≥0.5] (결정 때).
            # 경계 축은 [비경계, 경계]이고 vigilance 를 끈 세계는 모두 비경계 칸이다(v2.1 과 같은 수)
            self._gait_hist = np.zeros((2,) + GAIT_HIST_SHAPE, dtype=np.int64)
            self._sw = np.zeros(2, dtype=np.int64)            # 보행 전환 수 [실제, 명령] (B8)
            self._sw_steps = 0                                # 직전 스텝이 같은 개체인 개체-스텝
            self._gait_prev = np.full((2, self.N), -1, dtype=np.int8)   # 직전 [실제, 명령] 보행, −1 = 없음
            self._intake_sum = 0.0                            # 먹이로 얻은 에너지(상한에서 잘린 몫 제외)
            self._drain_sum = 0.0                             # 대사로 쓴 에너지
        if self._vg is not None:     # v2.2 경계 지표 (vigil_stats). 모두 개체-스텝 수·합이다
            self._vig_hist = np.zeros(VIG_HIST_SHAPE, dtype=np.int64)   # [구간 4, 결정 관측 시야 2, 배부름 2, 경계 2]
            self._vig_esum = np.zeros(4)               # B5 회귀: Σe, Σe², Σv, Σe·v (e = 결정 때 관측 4, v = 경계 0/1)
            self._vig_ema: list[float] = []            # B5′: 스텝마다 결정 때 관측 5(전역 값)와 경계 개체 수
            self._vig_ema_n: list[int] = []
            self._vig_kin = np.zeros(2)                # 결정 관측 시야별 동족 수·포식자 수 합 (360° 해석용, 4.2)
            self._vig_pc = np.zeros(2)
            self._vig_threat = 0.0                     # 결정 때 threat_recency 합
            self._vig_truth = np.zeros(VIG_TRUTH_SHAPE, dtype=np.int64)   # [기준 구간 3, 경계 2] (*_truth 열)
            # B4 [이동 도주·결정 관측 기본 FOV, 이동 도주·결정 관측 경계 시야, 경계한 도주 분기] × [표본, 다음 관측 안 보임]
            self._b4 = np.zeros((3, 2), dtype=np.int64)
            self._vsw, self._vsw_steps = 0, 0          # 경계 전환 수, 직전 스텝이 같은 개체인 개체-스텝
            self._vig_prev = np.full(self.N, -1, dtype=np.int8)
        if self._vw is not None:     # v2.2r 창 지표 (window_stats). 개체-스텝 수다
            self._win_hist = np.zeros(WINDOW_HIST_SHAPE, dtype=np.int64)   # [구간 3, 배부름 2, 실제 정지 2, 경계 2]
            self._win_look = 0                         # 반사 돌아보기가 돈 개체-스텝
        if self._dn is not None:     # v2.4 위상 지표 (daynight_stats). 위상 구간은 결정 때 어둠 d 다
            self._dn_hist = np.zeros(DN_HIST_SHAPE, dtype=np.int64)
            self._dn_b = np.zeros(DN_B_SHAPE, dtype=np.int64)
            self._dn_dead = np.zeros((2, 3), dtype=np.int64)    # [피식, 아사] × 위상
            self._dn_energy = np.zeros((2, 3))                  # [먹이 에너지, 대사] × 위상
            self._dn_dark = 0.0                                 # 스텝별 d 합
            self._dn_steps = 0
            if self._rp is not None:     # v3: 휴식·먹기 열의 행동 기준 판 [위상 3, 배부름 2, 결정 때 은신처 안 2, 먹이 셀 2, 행동]
                self._dn_rep = np.zeros((3, 2, 2, 2, rep.N_BEHAVIORS), dtype=np.int64)
        if self._rp is not None:     # v3 레퍼토리 지표 (repertoire_stats). 개체-스텝 수다
            self._rep_hist = np.zeros((3, 2, rep.N_BEHAVIORS), dtype=np.int64)   # [위상(낮·박명·밤), 위협 보임, 행동]
            self._rep_dead = np.zeros((2, rep.N_BEHAVIORS), dtype=np.int64)      # [피식, 아사] × 죽은 스텝의 행동
            self._rep_switch, self._rep_decide, self._rep_flicker = 0, 0, 0
            self._rep_before = np.full(self.N, -1, dtype=np.int64)              # 마지막 전환 전 행동(없으면 −1)
            self._rep_last_sw = np.full(self.N, -(10 ** 9), dtype=np.int64)     # 마지막 전환 스텝
            self._rep_flicker_w = int(FLICKER_SECONDS * 60.0 / float(self.cfg.policy_interval))
            self._rep_sw_slot = np.zeros(self.N, dtype=np.int64)                # 슬롯별 전환·깜빡임 수 (rep_slot_counts)
            self._rep_flick_slot = np.zeros(self.N, dtype=np.int64)
        if self._th is not None:     # v3 위협 지표 (threats_stats)
            self._th_catch = np.zeros(4, dtype=np.int64)    # 포획 수 [근접 추격, 원거리 추격, 잠행, 플레이어]
            self._th_pounce = np.zeros(2, dtype=np.int64)   # [돌진 시작, 돌진 포획]
            self._th_charge = 0                             # 플레이어 돌진 시작

    def _accumulate(self, a, rew, repro, caught, starved, done) -> None:
        self._rew_total += float(rew.sum())
        self._repro_total += int(repro.sum())
        self._pred_deaths += int(caught.sum())
        self._starve_deaths += int(starved.sum())
        self._life_cur += 1
        if done.any():
            self._life_sum += int(self._life_cur[done].sum())
            self._life_count += int(done.sum())
            self._life_cur[done] = 0
        self._agent_steps += self.N
        self._act_sum += a.sum(0)
        self._flee_sq += float((a[:, 2] ** 2).sum())
        self._cover_steps += int(self._g["in_cover"].sum())

        seen = self._g["pred_count"] > 0
        cols = a[:, [1, 2, 3]]
        self._a_pred += cols[seen].sum(0)
        self._n_pred += int(seen.sum())
        self._a_nopred += cols[~seen].sum(0)
        self._n_nopred += int((~seen).sum())

        hungry = self.energy < 0.5 * self.cfg.max_energy
        self._f_hungry += float(a[hungry, 0].sum())
        self._n_hungry += int(hungry.sum())
        self._f_full += float(a[~hungry, 0].sum())
        self._n_full += int((~hungry).sum())

    def _gait_accumulate(self, e_prev: np.ndarray, intake: np.ndarray, drain: np.ndarray) -> None:
        """v2.1 보행 지표를 센다. `step` 이 `_accumulate` 바로 뒤, 관측을 새로 계산하기 전에 부른다.

        조건(포식자 거리, 배고픔)은 정책이 이번 행동을 고를 때 본 상태다: 스텝 전 기하 `self._g`, 스텝 전 에너지
        `e_prev`(리스폰 직후 개체는 init_energy, 관측 4 와 같다). B1·B2 는 명령 보행으로 잰다 — 상태를 안 보는
        상수·순열 대조군에서 조건부 차이가 구성상 0 이 되게 한다(계획서 6.3 판정 규칙). 방향이 없어 실제로는
        멈춘 몫은 stall_frac 로 따로 낸다. v2.2 는 경계 축을 앞에 둔다(경계한 개체의 실제 보행은 정지다).
        """
        cfg = self.cfg
        g, cmd = self.gait, self.gait_cmd
        d = self._g["d_pred_min"] / cfg.see_r                  # 안 보이면 inf
        # 거리 구간: 안 보임 0, [0, 0.25) 1, [0.25, 0.5) 2, [0.5, 1] 3 (inf 는 두 문턱을 넘지만 seen 이 0 으로 만든다)
        b = (d < np.inf) * (1 + (d >= B1_EDGES[0]) + (d >= B1_EDGES[1]))
        full = e_prev >= HUNGRY * cfg.max_energy               # False 배고픔, True 배부름
        code = ((g * 3 + cmd) * 4 + b) * 2 + full               # GAIT_HIST_SHAPE 의 C 순서 평탄 인덱스
        if self._vg is not None:                                # 경계 축 (끈 세계는 모두 0 칸 — v2.1 과 같은 수)
            code = code + self.vigilant * int(np.prod(GAIT_HIST_SHAPE))
        self._gait_hist += np.bincount(code, minlength=self._gait_hist.size).reshape(self._gait_hist.shape)

        prev = self._gait_prev
        same = prev[0] >= 0
        self._sw_steps += int(np.count_nonzero(same))
        self._sw[0] += np.count_nonzero(same & (prev[0] != g))
        self._sw[1] += np.count_nonzero(same & (prev[1] != cmd))
        prev[0] = g
        prev[1] = cmd

        self._intake_sum += float(intake.sum())
        self._drain_sum += float(drain.sum())

    def gait_stats(self) -> dict:
        """v2.1 보행 통계 — reset 뒤 누적 (v1 `stats()` 10열 밖, 계획서 4.8). Gate E1 과 B1·B2·B8 이 쓴다.

        열 순서는 `GAIT_STAT_COLUMNS`. 비율은 모두 개체-스텝 기준이다. 분모가 0 인 열은 nan 이다.
        - stop_frac·walk_frac·run_frac: 실제 보행 비율(v2.2 경계는 속력 0 이라 정지에 든다. 경계 비율은 vigil_stats).
          stall_frac: 경계가 아닌데 명령은 이동이고 방향이 없어 정지한 비율
        - stop_frac_cmd·walk_frac_cmd·run_frac_cmd: 명령 보행(행동 idx 4 의 문턱) 비율. 경계 여부와 무관한 speed 명령이다
        - hungry_frac: 결정 때 energy < 0.5 인 비율 (Gate E1 (a) "energy<0.5 스텝")
        - starve_rate: 아사 / 개체-스텝, starve_share: 아사 / 사망 (env_v2/rollout.py 와 같은 정의)
        - b1 = P(뛰기 | 보임 & d < 0.5·see_r) − P(뛰기 | 안 보임). p_run_unseen, p_run_d025 [0, 0.25),
          p_run_d050 [0.25, 0.5), p_run_d100 [0.5, 1] (× see_r) 은 거리 구간별 P(뛰기) (6.2 B1). '뛰기' = 경계가 아니고
          명령이 뛰기(v2.2 는 경계가 speed 보다 우선이라 경계 개체는 뛰지 않는다). 분모는 경계 개체를 포함한다
        - b2 = P(정지 | 배고픔) − P(정지 | 배부름), p_stop_hungry·p_stop_full (6.2 B2 '경계가 아닌 정지': 경계가 아니고
          명령이 정지. v2.1 은 경계가 없어 모든 정지가 여기에 든다)
        - b8·b8_cmd: 개체당 초당 보행 전환 수(실제·명령). 직전 스텝이 같은 개체인 스텝만 센다. 1스텝 =
          policy_interval/60 초 (replay_v2.step_seconds 와 같은 정의, §9.7)
        - intake_per_step·drain_per_step: 개체-스텝당 먹이 에너지·대사
        vigilance 를 끈 세계는 경계 칸이 비어 v2.1 과 같은 값이다(정수 합).
        """
        if self._sp is None:
            raise ValueError("gait_stats 는 speed 를 켠 세계에만 있다 (끈 세계는 v1 과 같이 늘 herb_speed 로 움직인다)")
        nan = float("nan")
        n = self._agent_steps
        H = self._gait_hist.sum(0)                             # [실제, 명령, 거리 구간, 배부름] — 모든 개체
        H0 = self._gait_hist[0]                                # 같은 모양 — 경계가 아닌 개체

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        gait_n, cmd_n = H.sum((1, 2, 3)), H.sum((0, 2, 3))
        b1_n, b1_run = H.sum((0, 1, 3)), H0[:, GAIT_RUN].sum((0, 2))
        b2_n, b2_stop = H.sum((0, 1, 2)), H0[:, GAIT_STOP].sum((0, 1))
        stall = H0[GAIT_STOP, GAIT_WALK:].sum()
        p_run = [ratio(b1_run[k], b1_n[k]) for k in range(4)]
        near = ratio(b1_run[1] + b1_run[2], b1_n[1] + b1_n[2])
        p_stop = [ratio(b2_stop[k], b2_n[k]) for k in range(2)]
        deaths = self._pred_deaths + self._starve_deaths
        per_sec = 60.0 / float(self.cfg.policy_interval)
        out = dict(
            stop_frac=ratio(gait_n[0], n), walk_frac=ratio(gait_n[1], n),
            run_frac=ratio(gait_n[2], n), stall_frac=ratio(stall, n),
            stop_frac_cmd=ratio(cmd_n[0], n), walk_frac_cmd=ratio(cmd_n[1], n),
            run_frac_cmd=ratio(cmd_n[2], n),
            hungry_frac=ratio(b2_n[0], n),
            starve_rate=self._starve_deaths / max(self.t * self.N, 1),
            starve_share=ratio(self._starve_deaths, deaths),
            b1=near - p_run[0], p_run_unseen=p_run[0], p_run_d025=p_run[1], p_run_d050=p_run[2],
            p_run_d100=p_run[3],
            b2=p_stop[0] - p_stop[1], p_stop_hungry=p_stop[0], p_stop_full=p_stop[1],
            b8=ratio(self._sw[0], self._sw_steps) * per_sec, b8_cmd=ratio(self._sw[1], self._sw_steps) * per_sec,
            intake_per_step=ratio(self._intake_sum, n), drain_per_step=ratio(self._drain_sum, n),
        )
        assert tuple(out) == GAIT_STAT_COLUMNS
        return out

    def _vigil_accumulate(self, a: np.ndarray, e_prev: np.ndarray, ema0: float, moving: np.ndarray):
        """v2.2 경계 지표를 센다. `step` 이 `_accumulate` 뒤, 다음 관측의 시야(8a)와 관측(8)을 바꾸기 전에 부른다.

        조건은 정책이 이번 행동을 고를 때 본 상태다: 스텝 전 기하 `self._g`(포식자 수·동족 수), 결정 때 threat_recency
        (`self.threat`, 관측 7), 결정 관측의 시야(`self._wide`), 결정 때 에너지 `e_prev`(관측 4), 관측 5 `ema0`.
        경계는 이번 스텝에 적용된 `self.vigilant`(행동의 문턱이라 상수·순열 대조군에서 조건부 차이가 구성상 0).
        시야와 무관한 기준 구간은 결정 관측 때 저장한 `self._near`·`self._tr_truth`(`_perceive`)로 정한다 — 스텝이
        위치를 옮긴 뒤 다시 재지 않는다.
        반환: B4 표본 마스크 (이동 도주·결정 관측 기본 FOV, 이동 도주·결정 관측 경계 시야, 경계한 도주 분기) — 다음
        관측을 계산한 뒤 `_b4_accumulate` 가 센다.
        """
        cfg = self.cfg
        g, vig = self._g, self.vigilant
        pc = g["pred_count"]
        seen = pc > 0
        recent = ~seen & (self.threat > RECENT_THREAT)
        seg = np.where(seen, 2 + (pc >= 2), recent)            # 0 평시, 1 최근 위협·안 보임, 2 한 마리 보임, 3 둘 이상
        wide = self._wide
        full = e_prev >= HUNGRY * cfg.max_energy
        code = ((seg * 2 + wide) * 2 + full) * 2 + vig          # VIG_HIST_SHAPE 의 C 순서 평탄 인덱스
        self._vig_hist += np.bincount(code, minlength=self._vig_hist.size).reshape(VIG_HIST_SHAPE)
        e = np.clip(e_prev / cfg.max_energy, 0.0, 1.0)
        vf = vig.astype(np.float64)
        self._vig_esum += (e.sum(), (e * e).sum(), vf.sum(), (e * vf).sum())
        self._vig_ema.append(float(ema0))
        self._vig_ema_n.append(int(np.count_nonzero(vig)))
        self._vig_kin += np.bincount(wide, weights=g["kin_count"], minlength=2)
        self._vig_pc += np.bincount(wide, weights=pc, minlength=2)
        self._vig_threat += float(self.threat.sum())
        seg_t = np.where(self._near, 2, self._tr_truth > RECENT_THREAT)   # 0 평시, 1 최근 반경 안·지금 밖, 2 반경 안
        self._vig_truth += np.bincount(seg_t * 2 + vig, minlength=self._vig_truth.size).reshape(VIG_TRUTH_SHAPE)
        prev = self._vig_prev
        same = prev >= 0
        self._vsw_steps += int(np.count_nonzero(same))
        self._vsw += int(np.count_nonzero(same & (prev != vig)))
        prev[:] = vig
        branch = g["d_pred_min"] < a[:, 2] * cfg.see_r          # 도주 분기 (steer 와 같은 식)
        mv = branch & ~vig & moving
        return mv & ~wide, mv & wide, branch & vig

    def _b4_accumulate(self, flee: tuple, g_next: dict, done: np.ndarray) -> None:
        """B4: 도주 표본(`_vigil_accumulate` 의 마스크 3개) 중 다음 관측(스텝 끝 8)에서 포식자가 안 보인 수.
        이번 스텝에 죽은 개체는 뺀다."""
        lost = g_next["pred_count"] == 0
        for k, m in enumerate(flee):
            m = m & ~done
            self._b4[k, 0] += int(np.count_nonzero(m))
            self._b4[k, 1] += int(np.count_nonzero(m & lost))

    def vigil_stats(self) -> dict:
        """v2.2 경계 통계 — reset 뒤 누적 (v1 `stats()` 10열 밖, 계획서 4.8). Gate E2 와 B3·B4·B5·B5′ 이 쓴다.

        열 순서는 `VIGIL_STAT_COLUMNS`. 비율은 개체-스텝 기준이다(B4 는 표본 기준). 분모가 0 인 열은 nan 이다.
        구간(결정 때): 보임 = 포식자 수 > 0, 최근 위협 = 안 보임 & threat_recency > RECENT_THREAT(0.5), 평시 = 그 밖.

        주의 — 360° 치우침 (계획서 4.2 '360° 경계 중에는 kin_count·pred_count 도 늘어나므로 B 지표를 따로 본다',
        10-03 검토): 경계한 개체의 다음 결정 관측은 360° 라 '보임'·'최근 위협' 구간에 더 자주 든다. 그래서 경계가
        몇 스텝 이어지기만 하면(포식자를 전혀 보지 않는 정책이어도) 관측 구간으로 나눈 P(경계) 차가 행동이 아니라
        시야 때문에 커진다. 상수 정책·C1′(같은 스텝 개체끼리 행동 순열)는 경계의 지속을 끊어 이 치우침이 없으므로
        6.3 (1) 의 '대조군에서 구성상 0' 전제가 경계 지표에는 성립하지 않는다. 시야를 합친 b3·b5p_pred·p_vig_seen·
        p_vig_pc*·b4 는 기술용이고, 판정 후보는 *_narrow(결정 관측이 기본 FOV)·*_truth(시야와 무관한 기준 구간)다.
        1차 정의는 1-6 사전 등록에서 정한다. *_narrow 도 직전 한 스텝만 거른다 — threat 흔적을 통한 360° 선택 효과
        (예: 배고플수록 자주 경계하는 정책은 배고픈 개체가 최근 360° 로 포식자를 봐 '최근 위협'에 더 들고, 경계를
        시작하기도 쉽다)는 남는다. *_truth 는 시야 효과를 빼지만 경계가 위치(정지)를 통해 반경 안 여부를 바꾸는
        동역학 경로는 남는다.

        - vig_frac: 경계 비율. seg_*_frac: 구간 비율. p_vig_seen·p_vig_recent·p_vig_calm: 구간별 P(경계) (시야 합침)
        - b3 = P(경계 | 최근 위협·안 보임) − P(경계 | 평시) (6.2 B3, 시야 합침 — 경계 지속이 '최근 위협' 표본을 늘려
          치우친다). b3_narrow: 결정 관측이 기본 FOV 인 개체만(직전 스텝에 경계하지 않은 개체 — 경계를 '시작'하는 쪽)
        - b4 = 이동 도주(도주 분기 & 경계 아님 & 이번 스텝에 움직임) 중 다음 관측에서 포식자를 놓친 비율 (6.2 B4,
          시야 합침). b4_narrow: 그중 결정 관측이 기본 FOV 인 표본(결정·다음 관측 모두 120°) — **v1 기준선 59.1%
          (v1 은 늘 120°)와 비교하는 값은 b4_narrow 다.** b4_wide: 결정 관측이 경계 시야인 표본(직전 스텝 경계, 뒤쪽
          포식자로도 도주 분기에 들어가 다음 120° 관측에서 구성상 자주 놓친다. 보고만). b4_vig: 도주 분기에서 경계한
          개체가 놓친 비율. *_n 은 표본 수(죽은 개체 제외, b4_n = b4_narrow_n + b4_wide_n)
        - b5 = 결정 때 energy(관측 4)에 대한 경계(0/1) 최소제곱 기울기 (6.2 B5, 기대 −). p_vig_hungry·p_vig_full:
          energy < 0.5 / ≥ 0.5 의 P(경계). **관측적 기울기다(기술용).** 경계는 섭식 0 이라 경계를 이어 간 개체는
          energy 가 내려가고, 직전 뛰기(섭식 0·고대사)도 같은 쪽이다 — energy 를 보지 않는 지속·위협 반응 경계도
          b5 < 0 이 된다(역인과, 기대 부호와 같은 쪽이라 부호 기준이 자동 통과한다). 판정은 C4-energy(관측 4 고정·
          순열) 대비 차 또는 개입 곡선(diagnose_v2.intervention_curve, 관측 4)으로 한다(1-6 사전 등록)
        - B5′ (6.2, 기대 +. 1차로 쓸 정의는 1-6 사전 등록에서 정한다): b5p_pred = P(경계 | 포식자 보임) −
          P(경계 | 안 보임) (관측 기준, 360° 선택 효과 포함 — 포식자를 보지 않는 지속 경계도 + 로 치우친다),
          p_vig_pc0·pc1·pc2 = 포식자 0 / 1 / 2마리 이상일 때 P(경계). b5p_ema = recent_predation(관측 5, 전역 값) 상위
          20% 스텝 − 하위 20% 스텝의 P(경계) (스텝 분위수, diagnose_v2 '위험 높음/낮음'과 같은 분할. 전역 값이라 개체의
          시야와 무관하다)
        - *_narrow (결정 관측이 기본 FOV 인 개체만, 위 구간 그대로): p_vig_seen_narrow, p_vig_pc0_narrow·pc1·pc2,
          b5p_pred_narrow = p_vig_seen_narrow − p_vig_pc0_narrow
        - *_truth (시야와 무관한 기준 구간, 결정 때): 반경 안 = 결정 관측 위치에서 거리 ≤ see_r 인 포식자가 있다(FOV
          무시), 최근 = 반경 밖 & 흔적 > RECENT_THREAT(흔적은 threat_recency 와 같은 규칙·decay 를 반경 안 여부에
          적용한 통계 전용 값, 리스폰 0), 평시 = 그 밖. seg_near_truth_frac·seg_recent_truth_frac: 구간 비율,
          p_vig_near_truth·p_vig_recent_truth·p_vig_calm_truth: 구간별 P(경계), b3_truth = P(경계 | 최근) − P(경계 | 평시),
          b5p_truth = P(경계 | 반경 안) − P(경계 | 반경 밖)
        - b8_vig: 개체당 초당 경계 전환(켜기·끄기) 수. 직전 스텝이 같은 개체인 스텝만 센다(gait b8 과 같은 규칙)
        - 360° 해석용 (계획서 4.2 '경계 중에는 kin_count 와 pred_count 도 늘어난다'): obs_wide_frac = 결정 관측이 경계
          시야였던 비율, kin_narrow·kin_wide·pred_narrow·pred_wide = 시야별 평균 동족 수·포식자 수(관측 정규화 전)
        - threat_mean: 결정 때 threat_recency 평균
        """
        if self._vg is None:
            raise ValueError("vigil_stats 는 vigilance 를 켠 세계에만 있다")
        nan = float("nan")
        H = self._vig_hist                                      # [구간, 시야, 배부름, 경계]
        n = int(H.sum())

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        seg_n, seg_v = H.sum((1, 2, 3)), H[..., 1].sum((1, 2))
        nar_n, nar_v = H[:, 0].sum((1, 2)), H[:, 0, :, 1].sum(1)
        full_n, full_v = H.sum((0, 1, 3)), H[..., 1].sum((0, 1))
        wide_n = H.sum((0, 2, 3))
        p_calm, p_recent = ratio(seg_v[0], seg_n[0]), ratio(seg_v[1], seg_n[1])
        p_seen = ratio(seg_v[2] + seg_v[3], seg_n[2] + seg_n[3])
        p_pc0 = ratio(seg_v[0] + seg_v[1], seg_n[0] + seg_n[1])
        se, see, sv, sev = self._vig_esum
        var = see - se * se / n if n else 0.0
        b5 = (sev - se * sv / n) / var if n and var > 0.0 else nan
        ema = np.asarray(self._vig_ema)
        if len(ema):
            nv = np.asarray(self._vig_ema_n, dtype=np.float64)
            lo, hi = np.quantile(ema, [EMA_SPLIT_Q, 1.0 - EMA_SPLIT_Q])
            m_hi, m_lo = ema >= hi, ema <= lo
            b5p_ema = nv[m_hi].sum() / (self.N * m_hi.sum()) - nv[m_lo].sum() / (self.N * m_lo.sum())
        else:
            b5p_ema = nan
        per_sec = 60.0 / float(self.cfg.policy_interval)
        p_seen_n = ratio(nar_v[2] + nar_v[3], nar_n[2] + nar_n[3])
        p_pc0_n = ratio(nar_v[0] + nar_v[1], nar_n[0] + nar_n[1])
        B = self._b4                                            # [120° 결정 이동 도주, 360° 결정 이동 도주, 경계] × [표본, 놓침]
        T = self._vig_truth                                     # [기준 구간, 경계]
        tn, tv = T.sum(1), T[:, 1]
        p_t = [ratio(tv[k], tn[k]) for k in range(3)]           # 평시, 최근, 반경 안
        out = dict(
            vig_frac=ratio(seg_v.sum(), n),
            seg_seen_frac=ratio(seg_n[2] + seg_n[3], n), seg_recent_frac=ratio(seg_n[1], n),
            seg_calm_frac=ratio(seg_n[0], n),
            p_vig_seen=p_seen, p_vig_recent=p_recent, p_vig_calm=p_calm, b3=p_recent - p_calm,
            b3_narrow=ratio(nar_v[1], nar_n[1]) - ratio(nar_v[0], nar_n[0]),
            b4=ratio(B[0, 1] + B[1, 1], B[0, 0] + B[1, 0]), b4_n=float(B[0, 0] + B[1, 0]),
            b4_vig=ratio(B[2, 1], B[2, 0]), b4_vig_n=float(B[2, 0]),
            b5=b5, p_vig_hungry=ratio(full_v[0], full_n[0]), p_vig_full=ratio(full_v[1], full_n[1]),
            b5p_pred=p_seen - p_pc0, p_vig_pc0=p_pc0, p_vig_pc1=ratio(seg_v[2], seg_n[2]),
            p_vig_pc2=ratio(seg_v[3], seg_n[3]), b5p_ema=float(b5p_ema),
            b8_vig=ratio(self._vsw, self._vsw_steps) * per_sec,
            obs_wide_frac=ratio(wide_n[1], n),
            kin_narrow=ratio(self._vig_kin[0], wide_n[0]), kin_wide=ratio(self._vig_kin[1], wide_n[1]),
            pred_narrow=ratio(self._vig_pc[0], wide_n[0]), pred_wide=ratio(self._vig_pc[1], wide_n[1]),
            threat_mean=ratio(self._vig_threat, n),
            p_vig_seen_narrow=p_seen_n, p_vig_pc0_narrow=p_pc0_n, p_vig_pc1_narrow=ratio(nar_v[2], nar_n[2]),
            p_vig_pc2_narrow=ratio(nar_v[3], nar_n[3]), b5p_pred_narrow=p_seen_n - p_pc0_n,
            b4_narrow=ratio(B[0, 1], B[0, 0]), b4_narrow_n=float(B[0, 0]),
            b4_wide=ratio(B[1, 1], B[1, 0]), b4_wide_n=float(B[1, 0]),
            seg_near_truth_frac=ratio(tn[2], n), seg_recent_truth_frac=ratio(tn[1], n),
            p_vig_near_truth=p_t[2], p_vig_recent_truth=p_t[1], p_vig_calm_truth=p_t[0],
            b3_truth=p_t[1] - p_t[0], b5p_truth=p_t[2] - ratio(tv[0] + tv[1], tn[0] + tn[1]),
        )
        assert tuple(out) == VIGIL_STAT_COLUMNS
        return out

    def _window_accumulate(self, e_prev: np.ndarray) -> None:
        """v2.2r 창 지표를 센다. `step` 이 `_accumulate` 뒤, 관측(8)으로 `self._g` 를 바꾸기 전에 부른다.

        구간은 결정 때 상태다: 보임 = 결정 관측의 포식자 수 > 0, 창 = `self.window`(`step` 0, 동역학과 같은 theta),
        평시 = 그 밖. 배부름 = 결정 때 energy ≥ HUNGRY·max_energy. 정지 = 이번 스텝의 실제 보행 정지(경계 포함).
        """
        g = self._g
        seg = np.where(g["pred_count"] > 0, 2, self.window.astype(np.int64))   # 0 평시, 1 창 안, 2 보임
        full = e_prev >= HUNGRY * self.cfg.max_energy
        stop = (self.gait == GAIT_STOP) if self._sp is not None else self.vigilant
        code = ((seg * 2 + full) * 2 + stop) * 2 + self.vigilant   # WINDOW_HIST_SHAPE 의 C 순서 평탄 인덱스
        self._win_hist += np.bincount(code, minlength=self._win_hist.size).reshape(WINDOW_HIST_SHAPE)
        self._win_look += int(np.count_nonzero(self.looked))

    def window_stats(self) -> dict:
        """v2.2r 창 지표 — reset 뒤 누적 (수정 제안서 3.8 선택 규칙 (i)·B3 정의). 열 순서는 `WINDOW_STAT_COLUMNS`.

        비율은 개체-스텝 기준이고 분모가 0 이면 nan 이다. 창은 동역학의 theta 로 정한다.
        - win_frac: 결정 때 창 안 비율
        - p_stop_win·p_stop_calm: 창 안·평시의 P(실제 정지). *_full·*_hungry 는 결정 때 energy ≥ 0.5 / < 0.5 표본만
        - b3_l = p_stop_win_full − p_stop_calm_full — L 의 새 결정 사용 지표(B3_L). 배고파서 멈춘 경우를 떼려고
          배부른 표본만 쓴다. 상수 정책도 창 안·평시의 상태 분포 차이로 0 이 아닐 수 있다(대조군과 비교한다)
        - p_vig_win·p_vig_win_full·p_vig_win_hungry·p_vig_calm_w: 경계(효력이 난 경계) 비율. W′ 의 사용 지표는
          p_vig_win 이고, window_only 면 p_vig_calm_w 는 구성상 0 이다. action false 세계는 모두 0 이다.
          (평시 열 이름에 _w 를 붙인 것은 vigil_stats 의 p_vig_calm 과 rollout 행에서 겹치지 않게 하려는 것이다)
        - look_frac·look_win_frac: 반사 돌아보기가 돈 개체-스텝 비율(전체 대비, 창 안 대비). look_back 을 끄면 0
        """
        nan = float("nan")
        H = self._win_hist                                      # [구간, 배부름, 정지, 경계]
        n = int(H.sum())

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        sf = H.sum(3)                                           # [구간, 배부름, 정지]
        nf = sf.sum(2)                                          # [구간, 배부름]
        vf = H[..., 1].sum(2)                                   # [구간, 배부름] 경계 수

        def p_stop(k):
            return ratio(sf[k, :, 1].sum(), nf[k].sum())

        def p_stop_f(k, f):
            return ratio(sf[k, f, 1], nf[k, f])

        out = dict(
            win_frac=ratio(nf[1].sum(), n),
            p_stop_win=p_stop(1), p_stop_calm=p_stop(0),
            p_stop_win_full=p_stop_f(1, 1), p_stop_calm_full=p_stop_f(0, 1),
            b3_l=p_stop_f(1, 1) - p_stop_f(0, 1),
            p_stop_win_hungry=p_stop_f(1, 0), p_stop_calm_hungry=p_stop_f(0, 0),
            p_vig_win=ratio(vf[1].sum(), nf[1].sum()), p_vig_win_full=ratio(vf[1, 1], nf[1, 1]),
            p_vig_win_hungry=ratio(vf[1, 0], nf[1, 0]), p_vig_calm_w=ratio(vf[0].sum(), nf[0].sum()),
            look_frac=ratio(self._win_look, n), look_win_frac=ratio(self._win_look, nf[1].sum()),
        )
        assert tuple(out) == WINDOW_STAT_COLUMNS
        return out

    def _daynight_accumulate(self, e_prev, caught, starved, intake, drain) -> None:
        """v2.4 위상 지표를 센다. `step` 이 다른 누적 뒤, `_daynight_update`·관측(8) 전에 부른다.

        위상 구간은 이번 스텝 동역학이 쓴 결정 때 어둠 `self.dark` 다. 배부름·은신처 안·포식자 거리는 결정 때 상태
        (`e_prev`, 스텝 전 기하 `self._g`), 보행은 이번 스텝의 실제 보행(B1·B2 는 gait_stats 처럼 명령 보행), 먹이 셀은
        이번 스텝의 섭식 위치(이동 뒤 `self.pos`) 셀의 cap0 > 0 이다. 사망·섭취·대사는 이번 스텝 값이다.
        """
        cfg, g = self.cfg, self._g
        d = self.dark
        ph = 0 if d <= DN_EDGES[0] + DN_TOL else (2 if d >= DN_EDGES[1] - DN_TOL else 1)
        full = e_prev >= HUNGRY * cfg.max_energy
        vig = self.vigilant if self._vg is not None else np.zeros(self.N, dtype=bool)
        ix, iy = self._cell_index(self.pos)
        food_cell = self.food_cap[iy, ix] > 0.0
        code = ((((ph * 2 + full) * 2 + g["in_cover"]) * 3 + self.gait) * 2 + vig) * 2 + food_cell
        self._dn_hist += np.bincount(code, minlength=self._dn_hist.size).reshape(DN_HIST_SHAPE)
        if self._rp is not None:        # v3: 휴식·먹기 열의 행동 기준 판 (daynight_stats)
            code = (((ph * 2 + full) * 2 + g["in_cover"]) * 2 + food_cell) * rep.N_BEHAVIORS + self._rs.behavior
            self._dn_rep += np.bincount(code, minlength=self._dn_rep.size).reshape(self._dn_rep.shape)
        dd = g["d_pred_min"] / cfg.see_r
        b = (dd < np.inf) * (1 + (dd >= B1_EDGES[0]) + (dd >= B1_EDGES[1]))
        code = (((vig * 3 + ph) * 3 + self.gait_cmd) * 4 + b) * 2 + full
        self._dn_b += np.bincount(code, minlength=self._dn_b.size).reshape(DN_B_SHAPE)
        self._dn_dead[0, ph] += int(np.count_nonzero(caught))
        self._dn_dead[1, ph] += int(np.count_nonzero(starved))
        self._dn_energy[0, ph] += float(intake.sum())
        self._dn_energy[1, ph] += float(drain.sum())
        self._dn_dark += d
        self._dn_steps += 1

    def daynight_stats(self) -> dict:
        """v2.4 위상 지표 — reset 뒤 누적 (계획서 6.2 N1·N5′·N2, 2-5 행 Gate N). 열 순서는 `DAYNIGHT_STAT_COLUMNS`.

        위상 = 결정 때 어둠 d 의 구간(낮 d ≤ 0.2, 박명, 밤 d ≥ 0.8). 비율은 개체-스텝 기준이고 분모가 0 이면 nan 이다
        (낮 고정 세계는 밤 열이 nan 이다).
        - dn_period·dn_offset·dn_day_fixed·dn_induced: 이 세계의 T, 시작 위상, 낮 고정 여부, 시작 상태 유도 여부
        - dark_mean: 스텝 평균 d. frac_day·frac_twi·frac_night: 위상 구간 개체-스텝 비율
        - pred_rate_*·starve_rate_*: 위상 구간의 피식·아사 / 개체-스텝 (Gate N (a1)·(a3))
        - intake_*·drain_*: 개체-스텝당 먹이 에너지·대사. intake_ratio_nd = intake_night / intake_day (Gate N (a2))
        - p_rest_cover_*: P(결정 때 은신처 안 & 실제 정지 & 비경계). n1 = 밤 − 낮 (N1, 1차). 실제 보행이라 방향이 없어
          멈춘 개체(stall)도 든다 — 상수 정책에서도 정확히 0 은 아니다(C2 최대 +0.002, 10-06 검토)
        - p_eat_*_{hungry,full}: P(먹이 셀 & 실제 정지·걷기 & 비경계 | 위상, 결정 때 energy < 0.5 / ≥ 0.5).
          n5p = p_eat_night_hungry − p_eat_night_full (N5′ 원값). 상태 분포 효과로 상수 정책에서도 크게 음수라(배고픈 개체는
          먹이 밖에 있다) 1차 정의는 C1′(행동 순열) 대비 차다(results/v2/v2_4/PREREG.md 0절)
        - p_stop_*·p_run_*·p_cover_*: 실제 정지·뛰기·결정 때 은신처 안 비율. p_stop_night_{hungry,full}: 밤의 배고픔별 정지
        - b1_*·b2_*: gait_stats 의 B1·B2 를 위상 구간 안에서 잰 값(명령 보행, 경계 개체는 뛰지 않음·정지에서 뺀다)
        - n2: P(경계 | 밤, 안 보임) − P(경계 | 낮, 안 보임) (2차). vigilance 를 끈 세계는 nan
        repertoire(v3)를 켠 세계는 보행이 행동을 뜻하지 않으므로(FREEZE·HIDE·SLEEP 도 정지, 은신처 안 GRAZE 정지는 먹기다)
        휴식·먹기 열을 행동 기준으로 센다: p_rest_cover_*·n1 = P(결정 때 은신처 안 & SLEEP), p_eat_*·n5p = P(먹이 셀 & GRAZE).
        나머지 열(정지·뛰기·은신처 비율, B1·B2)은 실제 보행 그대로다.
        """
        nan = float("nan")
        H = self._dn_hist                                       # [위상, 배부름, 은신처, 보행, 경계, 먹이 셀]

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        n_ph = H.reshape(3, -1).sum(1)
        n_all = int(n_ph.sum())
        if self._rp is None:
            rest_cover = H[:, :, 1, GAIT_STOP, 0, :].sum((1, 2))
            eat = H[:, :, :, :2, 0, 1].sum((2, 3))              # [위상, 배부름] 먹이 셀 & 정지·걷기 & 비경계
        else:                                                   # [위상, 배부름, 은신처, 먹이 셀, 행동]
            rest_cover = self._dn_rep[:, :, 1, :, rep.SLEEP].sum((1, 2))
            eat = self._dn_rep[:, :, :, 1, rep.GRAZE].sum(2)
        n_pf = H.sum((2, 3, 4, 5))                               # [위상, 배부름]
        gait_ph = H.sum((1, 2, 4, 5))                            # [위상, 보행]
        cover_ph = H[:, :, 1].sum((1, 2, 3, 4))
        stop_pf = H[:, :, :, GAIT_STOP].sum((2, 3, 4))           # [위상, 배부름]

        B = self._dn_b                                          # [경계, 위상, 명령, 거리 구간, 배부름]
        Ball = B.sum(0)
        B0 = B[0]

        def b1(ph):
            near = Ball[ph, :, 1:3].sum((1, 2))                 # [명령] 보임 & d < 0.5
            un = Ball[ph, :, 0].sum(1)
            near_run = B0[ph, GAIT_RUN, 1:3].sum()
            un_run = B0[ph, GAIT_RUN, 0].sum()
            return ratio(near_run, near.sum()) - ratio(un_run, un.sum())

        def b2(ph):
            st = B0[ph, GAIT_STOP].sum(0)                        # [배부름] 경계 아닌 명령 정지
            nn = Ball[ph].sum((0, 1))
            return ratio(st[0], nn[0]) - ratio(st[1], nn[1])

        if self._vg is not None:
            unseen = Ball.sum(1)[:, 0].sum(1)                   # [위상] 안 보임 개체-스텝
            vig_un = B[1].sum(1)[:, 0].sum(1)
            n2 = ratio(vig_un[2], unseen[2]) - ratio(vig_un[0], unseen[0])
        else:
            n2 = nan
        e_day, e_twi, e_night = (self._dn_energy[0, k] for k in range(3))
        out = dict(
            dn_period=float(self.dn_period), dn_offset=float(self.dn_offset),
            dn_day_fixed=float(self.day_fixed), dn_induced=float(self.dn_induced),
            dark_mean=ratio(self._dn_dark, self._dn_steps),
            frac_day=ratio(n_ph[0], n_all), frac_twi=ratio(n_ph[1], n_all), frac_night=ratio(n_ph[2], n_all),
            pred_rate_day=ratio(self._dn_dead[0, 0], n_ph[0]), pred_rate_twi=ratio(self._dn_dead[0, 1], n_ph[1]),
            pred_rate_night=ratio(self._dn_dead[0, 2], n_ph[2]),
            starve_rate_day=ratio(self._dn_dead[1, 0], n_ph[0]), starve_rate_twi=ratio(self._dn_dead[1, 1], n_ph[1]),
            starve_rate_night=ratio(self._dn_dead[1, 2], n_ph[2]),
            intake_day=ratio(e_day, n_ph[0]), intake_twi=ratio(e_twi, n_ph[1]), intake_night=ratio(e_night, n_ph[2]),
            intake_ratio_nd=ratio(ratio(e_night, n_ph[2]), ratio(e_day, n_ph[0])) if n_ph[0] and n_ph[2] else nan,
            drain_day=ratio(self._dn_energy[1, 0], n_ph[0]), drain_night=ratio(self._dn_energy[1, 2], n_ph[2]),
            p_rest_cover_day=ratio(rest_cover[0], n_ph[0]), p_rest_cover_night=ratio(rest_cover[2], n_ph[2]),
            n1=ratio(rest_cover[2], n_ph[2]) - ratio(rest_cover[0], n_ph[0]),
            p_eat_night_hungry=ratio(eat[2, 0], n_pf[2, 0]), p_eat_night_full=ratio(eat[2, 1], n_pf[2, 1]),
            n5p=ratio(eat[2, 0], n_pf[2, 0]) - ratio(eat[2, 1], n_pf[2, 1]),
            p_eat_day_hungry=ratio(eat[0, 0], n_pf[0, 0]), p_eat_day_full=ratio(eat[0, 1], n_pf[0, 1]),
            p_stop_day=ratio(gait_ph[0, GAIT_STOP], n_ph[0]), p_stop_night=ratio(gait_ph[2, GAIT_STOP], n_ph[2]),
            p_run_day=ratio(gait_ph[0, GAIT_RUN], n_ph[0]), p_run_night=ratio(gait_ph[2, GAIT_RUN], n_ph[2]),
            p_cover_day=ratio(cover_ph[0], n_ph[0]), p_cover_night=ratio(cover_ph[2], n_ph[2]),
            p_stop_night_hungry=ratio(stop_pf[2, 0], n_pf[2, 0]), p_stop_night_full=ratio(stop_pf[2, 1], n_pf[2, 1]),
            b1_day=b1(0), b1_night=b1(2), b2_day=b2(0), b2_night=b2(2), n2=n2,
        )
        assert tuple(out) == DAYNIGHT_STAT_COLUMNS
        return out

    def pred_sleep_stats(self) -> dict:
        """v2.4s 포식자 잠 통계 — reset 뒤 누적. 열 순서는 `PSLEEP_STAT_COLUMNS`.
        pred_noct_frac: 이 세계의 야행성 비율 q, pred_noct_n: 야행성 포식자 수, pred_asleep_mean: 스텝 평균 자는 포식자 비율."""
        # v1 포식자만 센다(threats 의 플레이어 칸은 밤잠 배열에 야행성으로 들어 있다. 끈 세계는 M_base = M)
        out = dict(pred_noct_frac=float(self.pred_noct_frac),
                   pred_noct_n=float(self.pred_nocturnal[:self.M_base].sum()),
                   pred_asleep_mean=self._ps_asleep_sum / self._ps_steps if self._ps_steps else float("nan"))
        assert tuple(out) == PSLEEP_STAT_COLUMNS
        return out

    def _rep_accumulate(self, out: dict, caught: np.ndarray, starved: np.ndarray) -> None:
        """v3 레퍼토리 지표를 센다. `step` 이 `_accumulate` 바로 뒤, 시간을 넘기기(tick)·어둠 갱신·관측 전에 부른다.

        위상 구간은 결정 때 어둠(daynight_stats 와 같은 DN_EDGES), 위협 보임은 결정 관측의 포식자 수 > 0, 행동은 이번 스텝에
        실행한 행동이다. 깜빡임 = 행동이 A → B 로 바뀐 뒤 FLICKER_SECONDS(3초 = 22스텝) 안에 B → A 로 되돌아온 전환.
        """
        d = self.dark
        ph = 0 if d <= DN_EDGES[0] + DN_TOL else (2 if d >= DN_EDGES[1] - DN_TOL else 1)
        b = self._rs.behavior.astype(np.int64)
        seen = (self._g["pred_count"] > 0).astype(np.int64)
        K = rep.N_BEHAVIORS
        self._rep_hist[ph] += np.bincount(seen * K + b, minlength=2 * K).reshape(2, K)
        self._rep_dead[0] += np.bincount(b[caught], minlength=K)
        self._rep_dead[1] += np.bincount(b[starved], minlength=K)
        sw = out["switch"]
        self._rep_decide += int(np.count_nonzero(out["decide"]))
        if sw.any():
            i = np.flatnonzero(sw)
            self._rep_switch += len(i)
            t = self.t
            flick = (b[i] == self._rep_before[i]) & (t - self._rep_last_sw[i] <= self._rep_flicker_w)
            self._rep_flicker += int(np.count_nonzero(flick))
            self._rep_sw_slot[i] += 1
            self._rep_flick_slot[i[flick]] += 1
            self._rep_before[i] = out["prev"][i]
            self._rep_last_sw[i] = t

    def rep_slot_counts(self) -> dict:
        """슬롯별 행동 전환 수·깜빡임 수 (N,) int64 사본 — reset 뒤 누적, 같은 슬롯의 개체들을 합친다(repertoire_stats 의
        switch·flicker 와 같은 정의라 합이 같다). 침입 시험이 침입·거주로 나눠 쓴다."""
        if self._rp is None:
            raise ValueError("rep_slot_counts 는 repertoire 를 켠 세계에만 있다")
        return dict(switch=self._rep_sw_slot.copy(), flicker=self._rep_flick_slot.copy())

    def repertoire_stats(self) -> dict:
        """v3 레퍼토리 통계 — reset 뒤 누적. 열 순서는 `REP_STAT_COLUMNS`. 비율은 개체-스텝 기준, 분모가 0 이면 nan.

        - use_<행동>: 행동 사용 비율. use_day_·use_night_: 낮(d ≤ 0.2)·밤(d ≥ 0.8) 구간 안의 비율,
          use_seen_·use_unseen_: 결정 때 위협이 보인·안 보인 개체-스텝 안의 비율
        - pred_rate_<행동>·starve_rate_<행동>: 그 행동 중에 죽은 수(피식·아사) / 그 행동의 개체-스텝
        - seen_frac: 결정 때 위협이 보인 비율, switch_per_sec: 개체당 초당 행동 전환 수, flicker_rate: 전환 중 3초 안 A-B-A
          되돌림 비율, decide_frac: 결정 시점(잠금 끝 또는 사건 결정)인 개체-스텝 비율
        """
        if self._rp is None:
            raise ValueError("repertoire_stats 는 repertoire 를 켠 세계에만 있다")
        H = self._rep_hist                                      # [위상, 보임, 행동]
        n = int(H.sum())

        def ratio(x, y):
            return float(x) / float(y) if y else float("nan")

        tot, day, night = H.sum((0, 1)), H[0].sum(0), H[2].sum(0)
        seen, unseen = H[:, 1].sum(0), H[:, 0].sum(0)
        out = {}
        for pre, arr in (("use_", tot), ("use_day_", day), ("use_night_", night), ("use_seen_", seen),
                         ("use_unseen_", unseen)):
            for k, name in enumerate(rep.BEHAVIOR_NAMES):
                out[pre + name] = ratio(arr[k], arr.sum())
        for pre, row in (("pred_rate_", 0), ("starve_rate_", 1)):
            for k, name in enumerate(rep.BEHAVIOR_NAMES):
                out[pre + name] = ratio(self._rep_dead[row, k], tot[k])
        per_sec = 60.0 / float(self.cfg.policy_interval)
        out.update(seen_frac=ratio(seen.sum(), n), switch_per_sec=ratio(self._rep_switch, n) * per_sec,
                   flicker_rate=ratio(self._rep_flicker, self._rep_switch), decide_frac=ratio(self._rep_decide, n))
        assert tuple(out) == REP_STAT_COLUMNS
        return out

    def threats_stats(self) -> dict:
        """v3 위협 통계 — reset 뒤 누적. 열 순서는 `THREAT_STAT_COLUMNS`.
        p_stalk: 이 세계의 잠행형 비율(뽑은 값), stalker_n: 잠행형 수, player_present: 플레이어 유무(0/1),
        catch_rate_*: 유형별 포획 수 / 개체-스텝(근접 추격·원거리 추격·잠행·플레이어), pounce_n: 돌진 시작 수,
        pounce_hit: 돌진 중 포획 / 돌진 시작(없으면 nan), player_charge_n: 플레이어 돌진 시작 수."""
        if self._th is None:
            raise ValueError("threats_stats 는 threats 를 켠 세계에만 있다")
        n = max(self.t * self.N, 1)
        c, p = self._th_catch, self._th_pounce
        out = dict(p_stalk=float(self.threat_p_stalk), stalker_n=float(np.count_nonzero(self.pred_type == PT_STALKER)),
                   player_present=float(self.player_present),
                   catch_rate_chaser=c[0] / n, catch_rate_ranged=c[1] / n, catch_rate_stalker=c[2] / n,
                   catch_rate_player=c[3] / n, pounce_n=float(p[0]),
                   pounce_hit=float(p[1]) / float(p[0]) if p[0] else float("nan"),
                   player_charge_n=float(self._th_charge))
        assert tuple(out) == THREAT_STAT_COLUMNS
        return out

    def stats(self) -> dict:
        """§7.2 반환 열."""
        n, steps = self.N, max(self.t, 1)
        agent_steps = max(self._agent_steps, 1)
        lives = self._life_sum + int(self._life_cur.sum())
        n_lives = self._life_count + n
        flee_mean = self._act_sum[2] / agent_steps
        flee_var = max(self._flee_sq / agent_steps - flee_mean**2, 0.0)

        def _d(sum_a, n_a, sum_b, n_b):
            if n_a == 0 or n_b == 0:
                return float("nan")
            return float(np.abs(sum_a / n_a - sum_b / n_b).mean())

        if self._rp is not None:
            # repertoire(v3) 세계는 v1 조향 행동 열이 없어 cohesion_mean·flee_dist_mean·flee_dist_std·react_pred·react_hunger 가
            # nan 이다(0 이 실측처럼 보이지 않게. 행동 분포는 repertoire_stats). 열 순서는 v1 과 같다
            nan = float("nan")
            return dict(mean_return=self._rew_total / n, survival=lives / max(n_lives, 1),
                        repro=self._repro_total / n, predation_rate=self._pred_deaths / (steps * n),
                        cohesion_mean=nan, flee_dist_mean=nan, flee_dist_std=nan,
                        cover_frac=self._cover_steps / agent_steps, react_pred=nan, react_hunger=nan)
        return dict(
            mean_return=self._rew_total / n,
            survival=lives / max(n_lives, 1),
            repro=self._repro_total / n,
            predation_rate=self._pred_deaths / (steps * n),
            cohesion_mean=self._act_sum[1] / agent_steps,
            flee_dist_mean=flee_mean,
            flee_dist_std=float(np.sqrt(flee_var)),
            cover_frac=self._cover_steps / agent_steps,
            react_pred=_d(self._a_pred, self._n_pred, self._a_nopred, self._n_nopred),
            react_hunger=_d(
                np.array([self._f_hungry]),
                self._n_hungry,
                np.array([self._f_full]),
                self._n_full,
            ),
        )

    def food_stats(self) -> dict:
        """v2.0b 먹이 통계 — 지금 시점의 값 (v1 `stats()` 10열 밖, 계획서 4.8). Gate F·영상·기록 학습이 쓴다.

        지역은 v2.3 전까지 맵 좌우 절반(`_left_half`)으로 대신한다. 모두 cap0 > 0 셀만 센다.
        접미사 없음 = 맵 전체, `_left`·`_right` = 절반.
        - v_ratio, f_ratio: 지역 비율 ΣV/Σcap0, ΣF/Σcap0 (v2.3 지역 장부의 V_r·F_r 정의, 4.4)
        - v_cell_mean: 셀별 V/cap0 의 평균 (Gate F (a) "평균 V/cap0")
        - floor_frac: V/cap0 ≤ floor + FOOD_V_FLOOR_TOL 인 셀 비율 (Gate F (a) "하한에 붙은 셀")
        - eaten: reset 뒤 누적 섭취량의 합
        - half_life, rho, init_left, init_right: 이 세계에서 뽑은 회복 반감기와 V 초기 비율
        food_v 를 끈 세계는 V = cap0 로 본다(v_ratio 1). 하한·기록·뽑은 값이 없는 열은 nan 이다.
        절반에 cap0 > 0 셀이 없으면 그 절반의 열은 nan 이다.
        """
        on = self._fv is not None
        nan = float("nan")
        cap0, F = self.food_cap, self.food
        V = self.food_v if on else cap0
        pos = cap0 > 0.0
        left = self._left_half()
        out = dict(
            half_life=float(self.food_v_half_life) if on else nan,
            rho=float(self.food_v_rho) if on else nan,
            init_left=self.food_v_init[0] if on else nan,
            init_right=self.food_v_init[1] if on else nan,
        )
        tol = self._fv["floor"] + FOOD_V_FLOOR_TOL if on else nan
        for sfx, m in (("", pos), ("_left", pos & left), ("_right", pos & ~left)):
            c = cap0[m]
            s = float(c.sum())
            if s <= 0.0:
                for key in ("v_ratio", "f_ratio", "v_cell_mean", "floor_frac", "eaten"):
                    out[key + sfx] = nan
                continue
            vr = V[m] / c
            out["v_ratio" + sfx] = float(V[m].sum()) / s
            out["f_ratio" + sfx] = float(F[m].sum()) / s
            out["v_cell_mean" + sfx] = float(vr.mean())
            out["floor_frac" + sfx] = float((vr <= tol).mean()) if on else nan
            out["eaten" + sfx] = float(self._fv_eaten[m].sum()) if on else nan
        return out

    def food_cells(self) -> dict:
        """셀별 먹이 상태의 사본, 모두 (gw, gw) 이고 [iy, ix] 순서. Gate F (b) V 자기상관, (c) 흔적 진폭
        (누적 섭취 상위 10% 셀 vs 같은 cap0 구간 하위 50%, 섭식이 멈춘 뒤 경과), 영상의 짓밟힌 땅이 쓴다.

        - food_cap(cap0), food(F), food_v(V), left(왼쪽 절반), cover(은신처 셀)
        - eaten: reset 뒤 누적 섭취량, last_eat: 마지막으로 뜯긴 스텝의 self.t (뜯긴 적 없으면 −1)
        food_v 를 끈 세계는 food_v = cap0 사본이고 eaten·last_eat 는 None 이다.
        """
        on = self._fv is not None
        return dict(
            food_cap=self.food_cap.copy(),
            food=self.food.copy(),
            food_v=(self.food_v if on else self.food_cap).copy(),
            left=self._left_half(),
            cover=self.cover_cell.copy(),
            eaten=self._fv_eaten.copy() if on else None,
            last_eat=self._fv_last_eat.copy() if on else None,
        )
