"""v3 위협 모델 골든 내보내기 — 학습 세계의 위협 스텝을 언리얼 C++ `EcoThreatModel.h`(EcoThreatV3::Step)와 대조할 골든 헤더를 만든다
(계약 `Docs/RL_Policy/POLICY_CONTRACT_V3.md` 7·10·11절, 골든 G7).

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_threat.py
    # 시험용 다른 폴더
    python export_golden_v3_threat.py --out <폴더>

세계·사슴·시드:
  - 세계: configs/v3_r1_on.yaml (게임의 사슴 두뇌 R1b 가 배운 경보 없는 세계 — 사람 결정 10-13 (3)). 언리얼 늑대는 이 세계의 위협
    규칙을 따라야 한다(언리얼 ⊆ 학습 세계, 계약 7-7).
  - 사슴: R1b 출시 모델 ckpt/v3/v3_r1_g995_s3_20m.zip 의 argmax (env_v2/rollout.py RepLearned — 배포·판정 모드와 같다). 손 규칙이
    아니라 실제 출시 두뇌로 몰아야 FREEZE·웅크림·은신처 안 먹기 같은 체감 거리 배수가 게임과 같은 비율로 나온다.
  - 시드: 보정 시드 20000~20002 만 쓴다. 판정 시드(10000~10019, 10200~10219, 12160~12199)를 받으면 멈춘다.

골든 만드는 법:
  1) 롤아웃 기록: `World._step_predators_v3` 를 감싸 그 함수를 그대로 부르고, 위협 스텝마다 입력(초식 이동 뒤 위치·행동·HIDE 도착·
     은신처 안, 위협 상태, 어둠 d, 시각)과 그 스텝에 뽑힌 난수(배회 선회, 원거리 판정, 플레이어 새 모드)와 결과(위협 위치·heading·
     변위·쿨다운·잠행 상태·남은 스텝·플레이어 모드·남은 스텝, 포획)를 적는다. 난수는 감싼 생성기가 원래 생성기를 같은 인자로 부르므로
     궤적이 바뀌지 않는다(tests/test_threat_golden_v3.py 가 감싸지 않은 세계와 비트 단위로 같은지 본다). 표적·포획 판정은
     `_threat_motion`·`_threat_after` 를 감싸 world.py 가 계산한 has_target·d_t·got 을 그대로 받는다.
  2) 참조 스텝 `ref_step`: C++ Step 과 한 줄씩 같은 파이썬 함수다. 기록한 **모든** 위협 스텝(전체 초식 128)에서 world.py 결과와 같아야
     하고(정수·판정 정확, 실수 |Δ| ≤ 1e-12), 줄인 초식 목록으로 만든 골든 사례에서도 같아야 한다. 다르면 멈춘다.
  3) 초식 줄이기: 사례마다 초식을 표적·포획 반경 안 초식(반드시) + 체감 거리 ≤ KEEP_R(15) 인 초식을 가까운 순으로 MAX_PREY(16)까지
     (플레이어는 적어도 K_NEAR(3)마리)로 줄인다. 표적은 시야 중 체감 거리 최소이고 포획은 반경 안이라 결과가 바뀌지 않는다(2 가 확인).
     원래 초식 색인 순서를 지켜서 동점 규칙(낮은 색인)도 그대로다.
  4) 문턱 근처 제외(계약 11-2): 실거리·체감 거리 대 반경(위협 시야 14, 포획 1·3, 돌진 6) |d − r| < 1e-4, 위협 시야각 cos |c − cos 75°| <
     1e-5, 표적·포획 argmin 1·2위 차 0 < 차 < 1e-9, 벽 판정 0 < |새 위치 − 0 또는 size| < 1e-9 인 위협 스텝은 본 묶음·열에서 뺀다. 뺀 수를
     이유별로 헤더에 적고, 그중 몇 개는 '문턱 근처' 묶음(보고만)으로 싣는다. 구조상 **정확히** 같은 값은 빼지 않는다 — 어둠 d = 0.5
     (전환 스텝), 벽에 붙은 위협의 그 축 이동 0(새 위치 = 경계), 같은 자리 초식 둘의 거리 동점(낮은 색인 규칙). C++ 이 같은 순서로
     계산해 비트 단위로 같아야 한다.
  5) 끝 사례(무대): 실제 World 를 만들어 위협·초식·은신처·시각을 손으로 놓고 같은 `_step_predators_v3` 를 부른다(난수는 정한 값을
     내는 생성기). 문턱과 **정확히** 같은 거리(돌진 6, 포획 1·3, 시야 14 — 2 진수로 정확한 값), 바로 위(2^-12 위), 동점 규칙,
     행동별 은신 배수(SLEEP 포함 — 출시 두뇌에서는 나오지 않는다), 탈진 끝, 마지막 판정, 해 질 녘 잠(d = 0.5), 박명, 벽, 쿨다운
     1·2, 플레이어 모드 끝, 같은 자리 초식(거리 0)을 담는다. 무대 열(쿨다운 5 의 뜻: 잡음 → 4스텝 쉼 → 5번째 다시 잡음, 잠행형 한
     주기, 플레이어 돌진 한 주기, 해 질 녘·해 뜰 녘)도 같은 방법이다.

골든 묶음 (C++ 은 사례마다 Step 한 번, 열은 자기 출력 상태를 다음 스텝 입력으로 이어 붙인다):
  본 (롤아웃 한 스텝)  위협 종류(추격·원거리·잠행·플레이어)마다 상태·전이 표시(FLAG_NAMES)별로 PER_FLAG 개까지
  열 (롤아웃 이어진 스텝) 잠행형 돌진 주기, 플레이어 돌진 주기, 포획 뒤 쿨다운, 해 질 녘·해 뜰 녘
  끝 (무대 한 스텝)    위 5)
  무대 열              위 5)
  문턱 근처 (보고만)    위 4)

허용: 실수 |C++ − Python| ≤ 1e-4 (FLOAT_TOL), 정수·열거·판정은 정확히 같다.
결정성: 헤더에는 시각·절대 경로를 적지 않는다. 같은 모델·설정·코드면 바이트 단위로 같은 헤더가 나온다. torch 는 스레드 1 로 돈다.

계약과 코드의 차이 (코드가 이긴다 — 이 생성기와 C++ 은 코드를 따랐다):
  T1  계약 7-1 의 12 '원거리형 … 난수 (M_base, N)개': 판정 난수는 원거리형이 지금 있을 때가 아니라 **v1 이 뽑은 원거리형 배치**
      (잠행형이 덮기 전, `_pred_ranged_v1`)에 원거리형이 하나라도 있으면 뽑는다(world.py:2116). 잠행형이 원거리형을 모두 덮은 세계도
      난수를 뽑고 버린다(보정 시드 20000 이 그렇다). 난수 스트림 소비 모양일 뿐이라 C++ 동작과는 무관하다.
  T2  계약 7-1 의 5·7 은 시야 판정 뒤 선회 난수를 적었지만, 선회 난수는 상태와 무관하게 위협마다 늘 하나 뽑힌다(자는 위협·쿨다운·
      탈진·휴식 포함). C++ 은 WanderTurn 을 늘 받는다.
  T3  계약 7-5 '플레이어 CHARGE, 남은 > 0 … 표적 쪽': 표적이 없으면 head 그대로다(world.py:2333-2334). 플레이어는 맵 전체를 보므로
      표적이 없는 경우는 사냥하지 않을 때(쿨다운)뿐이다.
  T4  계약 7-2 표 'HIDE 도착(웅크림) 밖이면 det 1.8': 웅크림 = HIDE ∧ arrived 이고, arrived 는 이번 스텝 Arbiter 뒤 값이다. 은신처
      밖 HIDE 도착은 이번 스텝에 은신처를 나온 경우가 아니면 생기지 않는다(도착 판정이 in_cover 를 본다). 표 값은 맞다.
  T5  계약 7-6 '자는 위협은 … 초식 시야에서 빠진다'의 잠은 관측 때(스텝 끝, 새 t)의 d 로 다시 정한다. 위협 스텝 안의 잠은 결정 때
      d(t) 다. C++ FThreatState::bAsleep 훅은 위협 스텝 값이므로 관측에는 IsAsleep(새 d) 를 다시 부른다.
  T6  계약 11-2 표는 '실거리 대 반경'(위협 시야 14, 포획 1·3, stalk 6, 플레이어 돌진 6)이라 적었지만, 위협 쪽 비교는 실거리가 아니라
      체감 거리 perceived(시야 14·돌진 6)와 포획 거리 catch_d(포획 1·3)다(world.py:2055, 2115, 2300, 2316). 문턱 근처 제외는 실제로
      비교하는 값으로 했다.
  T7  계약에 없는 코드 동작 (C++ 도 그대로 따른다, 끝 사례 zero_dist_*): 위협과 같은 자리(거리 0)의 초식은 시야각 판정 값이 0 이라
      추격형·잠행형에게 보이지 않지만 포획 거리 0 이라 잡힌다. 플레이어는 맵 전체를 보므로 그 초식을 표적으로 잡고 move = 0 이 되어
      heading 이 영벡터가 된다(normalize 문턱 1e-9). 실제 롤아웃에서는 나오지 않았다.
  (계약 13-1 D3·D4·D10 은 계약이 이미 코드대로 고쳐 적었다: 표적 없는 잠행형은 기본 속력, 돌진 12 + 마지막 판정 1, 쿨다운 5 = 4스텝 쉼.)
"""

from __future__ import annotations

import env.torch_init  # noqa: F401  ← torch보다 먼저

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
UE_POLICY_DIR = ROOT.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
HEADER = "ThreatGoldenVectorsV3.h"
DEFAULT_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"     # R1b 출시 모델 (모델 시드 3)
DEFAULT_CONFIG = ROOT / "configs" / "v3_r1_on.yaml"               # R1 판정 세계 (경보 없음)

GOLDEN_SEEDS = (20000, 20001, 20002)     # 보정 시드 (export_weights_v3 와 같은 세 시드)
GOLDEN_STEPS = 3000
# 쓰면 안 되는 판정 시드 [시작, 끝) — 사전 등록 판정에 쓰는 범위
JUDGE_SEED_RANGES = ((10000, 10020), (10200, 10220), (12160, 12200))
STAGE_SEED = 20000                       # 무대 세계를 만드는 시드 (배치는 모두 덮어쓴다)

FLOAT_TOL = 1e-4                         # C++ 실수 허용 오차 (헤더에 적어 시험이 읽는다)
REF_TOL = 1e-12                          # 참조 스텝 대 world.py 실수 허용 (선회 cos·sin 의 마지막 비트 차만 남는다)
KEEP_R = 15.0                            # 초식 줄이기: 이 체감 거리 안 초식을 싣는다 (위협 시야 14 + 1)
MAX_PREY = 16                            # 사례당 초식 상한 (표적·포획 후보는 늘 싣는다)
K_NEAR = 3                               # 사례당 초식 하한 (플레이어는 맵 전체를 본다)
PER_FLAG = 6                             # 본 묶음: 위협 종류 × 표시마다 이만큼까지
N_NEAR_GROUP = 12                        # 문턱 근처 묶음 크기 (보고만)
SELECT_SEED = 7                          # 표본 고르기 난수 (결정적)

# 문턱 근처 제외 (계약 11-2)
EX_DIST = 1e-4
EX_COS = 1e-5
EX_TIE = 1e-9
EX_WALL = 1e-9
EX_REASONS = ("view_r", "fov", "catch_r", "stalk_dist", "charge_dist", "target_tie", "catch_tie", "wall")

KIND_MAIN, KIND_EDGE, KIND_SEQ, KIND_STAGE_SEQ, KIND_NEAR = 0, 1, 2, 3, 4
KIND_NAMES = ("본", "끝 사례", "롤아웃 열", "무대 열", "문턱 근처")
TYPE_KEYS = ("chaser", "ranged", "stalker", "player")

# 상태·전이 표시 (비트). 위협 종류마다 해당하는 것만 쓴다
FLAG_NAMES = (
    "asleep",             # 0  주행성 위협이 잔다 (d ≥ 0.5)
    "cooldown",           # 1  깨어 있고 쿨다운으로 사냥하지 않는다
    "wander",             # 2  사냥 중이고 표적이 없다 (배회)
    "target",             # 3  표적이 있다
    "catch",              # 4  잡았다
    "ranged_roll_miss",   # 5  원거리형: 포획 반경 안 초식이 있는데 난수로 못 잡았다
    "twilight",           # 6  깨어 있는 주행성, 0 < d < 0.5 (속력 × (1 − d))
    "night_active",       # 7  야행성·플레이어가 d ≥ 0.5 에 움직인다
    "wall",               # 8  벽 반사
    "dusk_exact",         # 9  d == 0.5 (전환 스텝, 정확히 같음)
    "stalking",           # 10 잠행형 ROAM 잠행 (표적 체감 > 6)
    "pounce_start",       # 11 잠행형 돌진 시작
    "pounce_dash",        # 12 돌진 (남은 > 0, 표적 있음, 시작 스텝 제외)
    "pounce_dash_blind",  # 13 돌진 (남은 > 0, 표적 없음 → head)
    "pounce_final_miss",  # 14 마지막 판정에서 놓침 → EXHAUST
    "pounce_catch",       # 15 돌진·마지막 판정 중 잡음 → ROAM
    "exhaust",            # 16 탈진 계속
    "exhaust_end",        # 17 탈진 끝 → ROAM
    "sleep_reset",        # 18 잠든 잠행형이 ROAM·0 으로 (돌진·탈진·남은 칸이 있었다)
    "p_wander",           # 19 플레이어 배회 모드
    "p_stalk",            # 20 플레이어 잠행 모드 (돌진 시작 아님)
    "p_charge_start",     # 21 플레이어 돌진 시작
    "p_charge_dash",      # 22 돌진 (남은 > 0, 시작 스텝 제외)
    "p_charge_final",     # 23 돌진 끝 판정 (남은 ≤ 0) → REST
    "p_charge_catch",     # 24 돌진 중 잡음 → REST
    "p_rest",             # 25 휴식 계속
    "p_rest_end",         # 26 휴식 끝 → 새 모드
    "p_mode_end",         # 27 배회·잠행 모드 길이 끝 → 새 모드
    "tie_exact",          # 28 표적 또는 포획 후보의 1·2위가 정확히 같다 (낮은 색인 규칙이 결과를 정한다)
)
FLAG = {n: 1 << i for i, n in enumerate(FLAG_NAMES)}
_COMMON = ("asleep", "cooldown", "wander", "target", "catch", "twilight", "night_active", "wall", "dusk_exact",
           "tie_exact")
TYPE_FLAGS = {
    "chaser": _COMMON,
    "ranged": _COMMON + ("ranged_roll_miss",),
    "stalker": _COMMON + ("stalking", "pounce_start", "pounce_dash", "pounce_dash_blind", "pounce_final_miss",
                          "pounce_catch", "exhaust", "exhaust_end", "sleep_reset"),
    "player": ("cooldown", "target", "catch", "night_active", "wall", "dusk_exact", "tie_exact", "p_wander", "p_stalk",
               "p_charge_start", "p_charge_dash", "p_charge_final", "p_charge_catch", "p_rest", "p_rest_end",
               "p_mode_end"),
}
# 결과 표시 비트 (kOutBits)
OUT_BITS = ("asleep", "hunting", "has_target", "wall", "pounce_start", "charge_start", "new_mode")
# 정수 상태 열 순서 (kPreInt·kPostInt)
INT_COLS = ("cd", "ss", "sl", "pm", "pl")
NO_ROLL = 2.0                            # 원거리 판정 난수가 없는 칸 (원거리형이 아니다)


def _w():
    from env_v2 import world as W
    return W


# --------------------------------------------------------------------- #
# 설정 상수
# --------------------------------------------------------------------- #


def cfg_constants(cfg) -> dict:
    """참조 스텝·헤더가 쓰는 학습 세계 상수 (World 가 검사한 계수). 키 순서 = 헤더 kCfg* 순서 = C++ FThreatConfig 칸 순서."""
    W = _w()
    w = W.World(cfg, seeds=[STAGE_SEED])
    rp, th, ps, dn = w._rp, w._th, w._ps, w._dn
    if rp is None or th is None or ps is None or dn is None:
        raise SystemExit("위협 골든은 repertoire·threats·pred_sleep·daynight 를 모두 켠 v3 세계에서만 만든다")
    if w._sd is not None or w._al is not None:
        raise SystemExit("위협 골든 세계에 stare_down(M7)·alarm(M8) 이 켜져 있다 — R1b 세계(configs/v3_r1_on.yaml)를 쓴다")
    if w._rz:
        raise SystemExit("위협 골든 세계에 realism_*(v3 현실성 1단계) 규칙이 켜져 있다 — C++ 에 아직 없는 규칙이다. "
                         "R1b 세계(configs/v3_r1_on.yaml)를 쓴다")
    rd = cfg.rand
    return {
        "HerbSpeed": float(cfg.herb_speed), "PredViewR": float(cfg.pred_view_r), "PredFovCos": float(cfg.pred_fov_cos),
        "PredMeleeCatchR": float(cfg.pred_melee_catch_r), "PredRangedCatchR": float(cfg.pred_ranged_catch_r),
        "PredRangedCatchP": float(cfg.pred_ranged_catch_p), "PredRangedSpeedMult": float(cfg.pred_ranged_speed_mult),
        "PredWanderTurn": float(cfg.pred_wander_turn), "PredEatCd": int(cfg.pred_eat_cd),
        "CStill": rp["c_still"], "CoverMultCrouch": rp["cover_mult_crouch"], "CoverMultGraze": rp["cover_mult_graze"],
        "CoverMultSleep": rp["cover_mult_sleep"], "CoverMultOther": rp["cover_mult_other"],
        "SleepDark": ps["sleep_dark"], "bTwilightSlow": bool(ps["twilight_slow"]),
        "StalkDist": th["stalk_dist"], "StalkSpeed": th["stalk_speed"], "PounceSpeed": th["pounce_speed"],
        "PounceSteps": th["pounce_steps"], "ExhaustSpeed": th["exhaust_speed"], "ExhaustSteps": th["exhaust_steps"],
        "PlayerSpeeds": tuple(th["player_speeds"]), "PlayerModeStepsLo": th["player_mode_steps"][0],
        "PlayerModeStepsHi": th["player_mode_steps"][1], "PlayerStalkP": th["player_stalk_p"],
        "PlayerChargeDist": th["player_charge_dist"], "PlayerChargeSteps": th["player_charge_steps"],
        "PlayerRestSteps": th["player_rest_steps"], "PlayerCatchR": th["player_catch_r"],
        "PlayerCooldown": th["player_cooldown"],
        "PredSpeedMultLo": float(rd["pred_speed_mult"][0]), "PredSpeedMultHi": float(rd["pred_speed_mult"][1]),
        "RangedFracLo": float(rd["ranged_frac"][0]), "RangedFracHi": float(rd["ranged_frac"][1]),
        "StalkFracLo": th["stalk_frac"][0], "StalkFracHi": th["stalk_frac"][1],
        "NocturnalFracLo": ps["nocturnal_frac"][0], "NocturnalFracHi": ps["nocturnal_frac"][1],
        "PlayerFrac": th["player_frac"], "PredatorCountLo": int(rd["predator_count"][0]),
        "PredatorCountHi": int(rd["predator_count"][1]), "WorldSizeLo": float(rd["world_size"][0]),
        "WorldSizeHi": float(rd["world_size"][1]), "DayPeriods": tuple(int(p) for p in dn["periods"]),
        "Twilight": float(w.features.params("daynight")["twilight"]),
    }


# --------------------------------------------------------------------- #
# 참조 스텝 (C++ EcoThreatV3::Step 과 한 줄씩 같다)
# --------------------------------------------------------------------- #


def ref_step(c: dict, spec: dict, st: dict, prey: dict, dark: float, size: float, turn: float, mode_u, roll):
    """위협 하나의 결정 스텝 (EcoThreatModel.h Step 의 거울). 반환 (새 상태, 결과, 진단).

    spec: type·ranged·noct·base_speed·catch_r, st: pos·head·cd·ss·sl·pm·pl, prey: x·y·beh·arrived·in_cover·alive (배열),
    roll: 초식마다 원거리 판정 난수 (원거리형이 아니면 None). mode_u: 플레이어 새 모드 난수 (u0, u1).
    """
    W = _w()
    from env_v2 import repertoire as rep
    from env_v2.steering import EPS

    stalker, player = spec["type"] == W.PT_STALKER, spec["type"] == W.PT_PLAYER
    qx, qy = float(st["pos"][0]), float(st["pos"][1])
    hx, hy = float(st["head"][0]), float(st["head"][1])
    cd, ss, sl, pm, pl = (int(st[k]) for k in INT_COLS)
    out = dict(pounce_start=False, charge_start=False, new_mode=False, wall=False)

    cd = max(cd - 1, 0)
    asleep = (not spec["noct"]) and dark >= c["SleepDark"]
    hunting = cd == 0 and not asleep
    if stalker and asleep:
        ss, sl = W.ST_ROAM, 0
    exh0 = stalker and ss == W.ST_EXHAUST
    rest0 = player and pm == W.PM_REST
    hunting = hunting and not exh0 and not rest0

    beh = np.asarray(prey["beh"])
    crouch = (beh == rep.HIDE) & np.asarray(prey["arrived"], dtype=bool)
    still = (beh == rep.FREEZE) | (beh == rep.SLEEP) | crouch
    cm = np.where(crouch, c["CoverMultCrouch"], np.where(beh == rep.GRAZE, c["CoverMultGraze"],
                                                         np.where(beh == rep.SLEEP, c["CoverMultSleep"],
                                                                  c["CoverMultOther"])))
    cov = np.where(np.asarray(prey["in_cover"], dtype=bool), cm, 1.0)
    det = np.maximum(cov, np.where(still, c["CStill"], 1.0))
    dx = np.asarray(prey["x"], dtype=np.float64) - qx
    dy = np.asarray(prey["y"], dtype=np.float64) - qy
    dist = np.sqrt(dx * dx + dy * dy)
    inv = 1.0 / np.maximum(dist, EPS)
    perceived = dist * det
    catch_d = dist * cov
    cosv = (dx * hx + dy * hy) * inv
    alive = np.asarray(prey["alive"], dtype=bool)
    vis = alive & hunting & (player | ((perceived <= c["PredViewR"]) & (cosv >= c["PredFovCos"])))
    masked = np.where(vis, perceived, np.inf)
    j = int(np.argmin(masked)) if len(masked) else 0
    has_target = bool(len(masked) and np.isfinite(masked[j]))
    d_t = float(masked[j]) if has_target else math.inf

    tv = np.cos(np.array([turn], dtype=np.float64))[0], np.sin(np.array([turn], dtype=np.float64))[0]
    wx, wy = hx * tv[0] - hy * tv[1], hx * tv[1] + hy * tv[0]
    mx, my = (float(dx[j] * inv[j]), float(dy[j] * inv[j])) if has_target else (wx, wy)
    speed = float(spec["base_speed"])
    hs = c["HerbSpeed"]

    final = dash = stalking = False
    if stalker:
        roam = ss == W.ST_ROAM
        start = roam and has_target and d_t <= c["StalkDist"]
        if start:
            ss, sl = W.ST_POUNCE, c["PounceSteps"]
            out["pounce_start"] = True
        stalking = roam and has_target and not start
        pounce = ss == W.ST_POUNCE
        final = pounce and sl <= 0
        dash = pounce and not final
        if stalking:
            speed = c["StalkSpeed"] * hs
        if dash:
            speed = c["PounceSpeed"] * hs
        if exh0 or final:
            speed = c["ExhaustSpeed"] * hs
        if (dash and not has_target) or final:
            mx, my = hx, hy
    pm_motion, pl_motion = pm, pl
    if player:
        if pm == W.PM_STALK and has_target and d_t <= c["PlayerChargeDist"]:
            pm, pl = W.PM_CHARGE, c["PlayerChargeSteps"]
            out["charge_start"] = True
        pm_motion, pl_motion = pm, pl
        ps = c["PlayerSpeeds"]
        if pm == W.PM_WANDER:
            speed, mx, my = ps[0] * hs, wx, wy
        elif pm == W.PM_STALK:
            speed = ps[1] * hs
        elif pm == W.PM_CHARGE and pl > 0:
            speed = ps[2] * hs
            if not has_target:
                mx, my = hx, hy
        else:
            speed, mx, my = 0.0, hx, hy
    if asleep:
        mx, my = hx, hy
    mult = 0.0 if asleep else ((1.0 - dark if c["bTwilightSlow"] else 1.0) if not spec["noct"] else 1.0)
    speed = speed * mult

    nx, ny = qx + mx * speed, qy + my * speed
    raw = (nx, ny)
    if nx < 0.0 or nx > size:
        mx = -mx
        out["wall"] = True
    if ny < 0.0 or ny > size:
        my = -my
        out["wall"] = True
    nx = min(max(nx, 0.0), size)
    ny = min(max(ny, 0.0), size)
    n = math.sqrt(mx * mx + my * my)
    hx2, hy2 = (mx / n, my / n) if n > EPS else (0.0, 0.0)

    ok_roll = np.ones(len(dist), dtype=bool)
    if spec["ranged"]:
        ok_roll = (np.asarray(roll, dtype=np.float64) < c["PredRangedCatchP"]) if roll is not None else ~ok_roll
    hit = alive & hunting & (catch_d <= spec["catch_r"]) & ok_roll
    hit_d = np.where(hit, catch_d, np.inf)
    k = int(np.argmin(hit_d)) if len(hit_d) else 0
    got = bool(len(hit_d) and np.isfinite(hit_d[k]))
    if got:
        cd = c["PlayerCooldown"] if player else c["PredEatCd"]

    if stalker:
        if ss == W.ST_POUNCE and got:
            ss, sl = W.ST_ROAM, 0
        if final and not got:
            ss, sl = (W.ST_EXHAUST if c["ExhaustSteps"] > 0 else W.ST_ROAM), c["ExhaustSteps"]
        if dash and not got:
            sl -= 1
        if exh0:
            sl -= 1
            if sl <= 0:
                ss, sl = W.ST_ROAM, 0

    def new_mode():
        lo, hi = c["PlayerModeStepsLo"], c["PlayerModeStepsHi"]
        m_ = W.PM_STALK if mode_u[0] < c["PlayerStalkP"] else W.PM_WANDER
        return m_, min(lo + int(mode_u[1] * (hi - lo + 1)), hi)

    if player:
        if pm == W.PM_CHARGE:
            if got or pl <= 0:
                pm, pl = W.PM_REST, c["PlayerRestSteps"]
                if c["PlayerRestSteps"] <= 0:
                    pm, pl = new_mode()
                    out["new_mode"] = True
            else:
                pl -= 1
        else:
            pl -= 1
            if pl <= 0:
                pm, pl = new_mode()
                out["new_mode"] = True

    post = dict(pos=(nx, ny), head=(hx2, hy2), vel=(nx - qx, ny - qy), cd=cd, ss=ss, sl=sl, pm=pm, pl=pl)
    out.update(asleep=asleep, hunting=hunting, has_target=has_target, target=j if has_target else -1,
               d_t=d_t if has_target else -1.0, caught=k if got else -1, speed=speed)
    diag = dict(perceived=perceived, catch_d=catch_d, cosv=cosv, vis=vis, hit=hit, ok_roll=ok_roll, raw=raw,
                final=final, dash=dash, stalking=stalking, exh0=exh0, rest0=rest0, pm_motion=pm_motion,
                pl_motion=pl_motion, d_t=d_t)
    return post, out, diag


# --------------------------------------------------------------------- #
# 기록 (world.py 를 감싸 그대로 부른다)
# --------------------------------------------------------------------- #


class _Tap:
    """난수 생성기 감싸기: 원래 생성기를 같은 인자로 부르고 결과를 적는다(궤적이 바뀌지 않는다). 다른 메서드는 막는다."""

    def __init__(self, g, log: list, tag: str):
        self._g, self._log, self._tag = g, log, tag

    def uniform(self, *a, **k):
        x = self._g.uniform(*a, **k)
        self._log.append((self._tag, "uniform", np.array(x, dtype=np.float64, copy=True)))
        return x

    def random(self, *a, **k):
        x = self._g.random(*a, **k)
        self._log.append((self._tag, "random", np.array(x, dtype=np.float64, copy=True)))
        return x

    def __getattr__(self, name):
        raise AttributeError(f"위협 스텝 기록: 예상하지 못한 난수 호출 {self._tag}.{name}")


class _Script:
    """무대용 난수: 정한 값을 낸다. uniform(lo, hi, n) 은 turns 앞 n 개, random(shape) 는 큐의 다음 배열 (모양 확인)."""

    def __init__(self, turns=(), randoms=()):
        self._turns = list(turns)
        self._randoms = list(randoms)

    def uniform(self, lo, hi, n):
        if n > len(self._turns):
            raise RuntimeError("무대 난수: 선회 값이 모자란다")
        x = np.array(self._turns[:n], dtype=np.float64)
        self._turns = self._turns[n:]
        if np.any(x < lo) or np.any(x > hi):
            raise RuntimeError(f"무대 선회 값이 [{lo}, {hi}] 밖이다: {x}")
        return x

    def random(self, shape):
        if not self._randoms:
            raise RuntimeError("무대 난수: random 값이 없다")
        x = np.asarray(self._randoms.pop(0), dtype=np.float64)
        if x.shape != tuple(np.atleast_1d(shape)):
            raise RuntimeError(f"무대 난수 모양 {x.shape} 이 {shape} 와 다르다")
        return x


class Recorder:
    """World 하나의 위협 스텝을 기록한다. `_step_predators_v3`·`_threat_motion`·`_threat_after` 를 인스턴스에서만 감싸고, 원래
    함수를 그대로 부른다. 기록 하나 = 세계 스텝 하나(모든 위협)."""

    def __init__(self, w):
        self.w = w
        self.records = []
        self._orig_step = w._step_predators_v3
        self._orig_tm = w._threat_motion
        self._orig_ta = w._threat_after
        w._step_predators_v3 = self._step
        w._threat_motion = self._tm
        w._threat_after = self._ta
        self._cap = None

    def detach(self) -> None:
        w = self.w
        for name in ("_step_predators_v3", "_threat_motion", "_threat_after"):
            w.__dict__.pop(name, None)

    def _tm(self, move, speed, wander, has_target, d_t, exh0, rest0):
        self._cap.update(has_target=np.array(has_target, copy=True), d_t=np.array(d_t, copy=True))
        mv, sp, ts = self._orig_tm(move, speed, wander, has_target, d_t, exh0, rest0)
        self._cap["speed_tm"] = np.array(sp, dtype=np.float64, copy=True)
        return mv, sp, ts

    def _ta(self, got, ts):
        self._cap["got"] = np.array(got, dtype=bool, copy=True)
        return self._orig_ta(got, ts)

    def _step(self):
        w = self.w
        pre = dict(
            t=int(w.t), dark=float(w.dark), size=float(w.size), period=int(w.dn_period), offset=int(w.dn_offset),
            tw=int(w.dn_tw), day_fixed=bool(w.day_fixed),
            pos=np.array(w.pos, dtype=np.float64, copy=True), beh=np.array(w._rs.behavior, dtype=np.int64, copy=True),
            arrived=np.array(w._rs.arrived, dtype=bool, copy=True), still=np.array(w._rep_still, dtype=bool, copy=True),
            cover=np.array(w._rep_cover, dtype=np.float64, copy=True), in_cover=np.array(w._in_cover(w.pos), copy=True),
            pred_pos=w.pred_pos.copy(), pred_head=w.pred_head.copy(), cd=w.pred_cd.astype(np.int64),
            ss=w.stalk_state.astype(np.int64), sl=w.stalk_left.astype(np.int64), pm=w.player_mode.astype(np.int64),
            pl=w.player_left.astype(np.int64), asleep=w.pred_asleep.copy(), smult=w._pred_speed_mult.copy(),
            type=w.pred_type.astype(np.int64), ranged=w.pred_ranged.copy(), noct=w.pred_nocturnal.copy(),
            speed=w.pred_speed.astype(np.float64), catch_r=w.pred_catch_r.astype(np.float64),
            mult=float(w.pred_speed_mult), M=int(w.M), Mb=int(w.M_base), seed=int(w.seed))
        log = []
        g1 = w.rng
        g2, g3 = w.feature_rng("threats", 2), w.feature_rng("threats", 3)
        w.rng = _Tap(g1, log, "v1")
        w._feature_rngs[("threats", 2)] = _Tap(g2, log, "t2")
        w._feature_rngs[("threats", 3)] = _Tap(g3, log, "t3")
        self._cap = {}
        try:
            caught = self._orig_step()
        finally:
            w.rng = g1
            w._feature_rngs[("threats", 2)] = g2
            w._feature_rngs[("threats", 3)] = g3
        post = dict(pred_pos=w.pred_pos.copy(), pred_head=w.pred_head.copy(), pred_vel=w.pred_vel.copy(),
                    cd=w.pred_cd.astype(np.int64), ss=w.stalk_state.astype(np.int64), sl=w.stalk_left.astype(np.int64),
                    pm=w.player_mode.astype(np.int64), pl=w.player_left.astype(np.int64))
        M, Mb, N = pre["M"], pre["Mb"], len(pre["pos"])
        rng = dict(turn=None, rolls=None, pturn=np.zeros(0), mode=None)
        for tag, kind, x in log:
            if tag == "v1" and kind == "uniform" and rng["turn"] is None:
                rng["turn"] = x
            elif tag == "v1" and kind == "random" and rng["rolls"] is None:
                rng["rolls"] = x
            elif tag == "t3" and kind == "uniform" and len(rng["pturn"]) == 0:
                rng["pturn"] = x
            elif tag == "t2" and kind == "random" and rng["mode"] is None:
                rng["mode"] = x
            else:
                raise SystemExit(f"위협 스텝 난수 모양이 예상과 다르다: {[(a, b, np.shape(c)) for a, b, c in log]}")
        if rng["turn"] is None or len(rng["turn"]) != Mb or len(rng["pturn"]) != M - Mb:
            raise SystemExit("위협 스텝 선회 난수 수가 위협 수와 다르다")
        if rng["rolls"] is not None and rng["rolls"].shape != (Mb, N):
            raise SystemExit("원거리 판정 난수 모양이 (M_base, N) 이 아니다")
        # 저장: 원거리 판정 난수는 지금 원거리형인 행만 남긴다(메모리)
        rolls = rng["rolls"]
        keep_rolls = {int(m): rolls[m].copy() for m in np.flatnonzero(pre["ranged"][:Mb])} if rolls is not None else {}
        rec = dict(pre=pre, post=post, turns=np.concatenate([rng["turn"], rng["pturn"]]), rolls=keep_rolls,
                   rolls_drawn=rolls is not None, mode=rng["mode"], cap=self._cap, caught=np.array(caught, copy=True))
        self.records.append(rec)
        return caught


# --------------------------------------------------------------------- #
# 기록 → 위협 사례
# --------------------------------------------------------------------- #


def type_key(rec, m) -> str:
    W = _w()
    p = rec["pre"]
    t = int(p["type"][m])
    if t == W.PT_PLAYER:
        return "player"
    if t == W.PT_STALKER:
        return "stalker"
    return "ranged" if bool(p["ranged"][m]) else "chaser"


def threat_inputs(rec, m, idx=None) -> dict:
    """기록 하나의 위협 m 입력 (idx = 실을 초식 색인, None 이면 전체)."""
    W = _w()
    p = rec["pre"]
    n = len(p["pos"])
    idx = np.arange(n) if idx is None else np.asarray(idx, dtype=np.int64)
    player = int(p["type"][m]) == W.PT_PLAYER
    spec = dict(type=int(p["type"][m]), ranged=bool(p["ranged"][m]), noct=bool(p["noct"][m]),
                base_speed=float(p["speed"][m]), catch_r=float(p["catch_r"][m]), mult=float(p["mult"]))
    st = dict(pos=tuple(map(float, p["pred_pos"][m])), head=tuple(map(float, p["pred_head"][m])),
              cd=int(p["cd"][m]), ss=int(p["ss"][m]), sl=int(p["sl"][m]), pm=int(p["pm"][m]), pl=int(p["pl"][m]))
    prey = dict(x=p["pos"][idx, 0].copy(), y=p["pos"][idx, 1].copy(), beh=p["beh"][idx].copy(),
                arrived=p["arrived"][idx].copy(), in_cover=p["in_cover"][idx].copy(),
                alive=np.ones(len(idx), dtype=bool), slot=idx.copy())
    roll = rec["rolls"][m][idx].copy() if m in rec["rolls"] else None
    mode = rec["mode"] if (player and rec["mode"] is not None) else None
    return dict(spec=spec, st=st, prey=prey, roll=roll, dark=float(p["dark"]), size=float(p["size"]),
                turn=float(rec["turns"][m]), mode_u=(float(mode[0]), float(mode[1])) if mode is not None else (0.0, 0.0),
                new_mode=mode is not None, clock=(int(p["t"]), int(p["period"]), int(p["offset"]), int(p["tw"])))


def env_result(rec, m) -> dict:
    """world.py 가 낸 위협 m 의 결과."""
    p, q, cap = rec["pre"], rec["post"], rec["cap"]
    post = dict(pos=tuple(map(float, q["pred_pos"][m])), head=tuple(map(float, q["pred_head"][m])),
                vel=tuple(map(float, q["pred_vel"][m])), cd=int(q["cd"][m]), ss=int(q["ss"][m]), sl=int(q["sl"][m]),
                pm=int(q["pm"][m]), pl=int(q["pl"][m]))
    has_target = bool(cap["has_target"][m])
    out = dict(asleep=bool(p["asleep"][m]), has_target=has_target,
               d_t=float(cap["d_t"][m]) if has_target else -1.0, got=bool(cap["got"][m]),
               speed=float(cap["speed_tm"][m] * p["smult"][m]))
    return dict(post=post, out=out)


def _close(a, b, tol) -> bool:
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def check_ref(inp: dict, env: dict, post: dict, out: dict, where: str) -> None:
    """참조 스텝 결과가 world.py 결과와 같은지 (정수·판정 정확, 실수 REF_TOL). 다르면 멈춘다."""
    e_post, e_out = env["post"], env["out"]
    bad = []
    for k in INT_COLS:
        if post[k] != e_post[k]:
            bad.append(f"{k} {post[k]} != {e_post[k]}")
    for k in ("pos", "head", "vel"):
        if not _close(post[k], e_post[k], REF_TOL):
            bad.append(f"{k} {post[k]} != {e_post[k]}")
    if out["asleep"] != e_out["asleep"] or out["has_target"] != e_out["has_target"]:
        bad.append(f"asleep/has_target {out['asleep']},{out['has_target']} != {e_out['asleep']},{e_out['has_target']}")
    if out["has_target"] and out["d_t"] != e_out["d_t"]:
        bad.append(f"d_t {out['d_t']} != {e_out['d_t']}")
    if (out["caught"] >= 0) != e_out["got"]:
        bad.append(f"got {out['caught']} vs {e_out['got']}")
    if abs(out["speed"] - e_out["speed"]) > REF_TOL:
        bad.append(f"speed {out['speed']} != {e_out['speed']}")
    if out["new_mode"] != inp["new_mode"]:
        bad.append(f"new_mode {out['new_mode']} != {inp['new_mode']}")
    if bad:
        raise SystemExit(f"참조 스텝이 world.py 와 다르다 ({where}): " + "; ".join(bad))


def check_chain(name: str, cases: list) -> None:
    """열: 앞 스텝의 world.py 결과 상태가 다음 스텝 입력 상태와 비트 단위로 같아야 한다(C++ 이 자기 출력을 이어 쓰는 근거)."""
    for a, b in zip(cases, cases[1:]):
        st = b["inp"]["st"]
        if not (a["post"]["pos"] == st["pos"] and a["post"]["head"] == st["head"]
                and all(a["post"][k] == st[k] for k in INT_COLS)):
            raise SystemExit(f"열 {name}: 앞 스텝 결과가 다음 스텝 입력과 다르다")


def run_ref(c, inp):
    return ref_step(c, inp["spec"], inp["st"], inp["prey"], inp["dark"], inp["size"], inp["turn"], inp["mode_u"],
                    inp["roll"])


def near_reasons(c, inp, out, diag) -> int:
    """문턱 근처 이유 비트 (EX_REASONS 순서). 0 이면 본 묶음에 실을 수 있다."""
    W = _w()
    spec, st = inp["spec"], inp["st"]
    player = spec["type"] == W.PT_PLAYER
    stalker = spec["type"] == W.PT_STALKER
    alive = np.asarray(inp["prey"]["alive"], dtype=bool)
    per, cat, cosv = diag["perceived"][alive], diag["catch_d"][alive], diag["cosv"][alive]
    r = 0
    if out["hunting"]:
        if not player:
            if np.any(np.abs(per - c["PredViewR"]) < EX_DIST):
                r |= 1 << EX_REASONS.index("view_r")
            m = per <= c["PredViewR"] + EX_DIST
            if np.any(np.abs(cosv[m] - c["PredFovCos"]) < EX_COS):
                r |= 1 << EX_REASONS.index("fov")
        if np.any(np.abs(cat - spec["catch_r"]) < EX_DIST):
            r |= 1 << EX_REASONS.index("catch_r")
        v = np.sort(diag["perceived"][diag["vis"]])
        if len(v) >= 2 and 0.0 < v[1] - v[0] < EX_TIE:
            r |= 1 << EX_REASONS.index("target_tie")
        h = np.sort(diag["catch_d"][diag["hit"]])
        if len(h) >= 2 and 0.0 < h[1] - h[0] < EX_TIE:
            r |= 1 << EX_REASONS.index("catch_tie")
    if out["has_target"]:
        ss_now = W.ST_ROAM if (stalker and out["asleep"]) else st["ss"]
        if stalker and ss_now == W.ST_ROAM and abs(out["d_t"] - c["StalkDist"]) < EX_DIST:
            r |= 1 << EX_REASONS.index("stalk_dist")
        if player and st["pm"] == W.PM_STALK and abs(out["d_t"] - c["PlayerChargeDist"]) < EX_DIST:
            r |= 1 << EX_REASONS.index("charge_dist")
    for x in diag["raw"]:
        if 0.0 < abs(x) < EX_WALL or 0.0 < abs(x - inp["size"]) < EX_WALL:
            r |= 1 << EX_REASONS.index("wall")
    return r


def flags_of(c, inp, post, out, diag) -> int:
    W = _w()
    spec, st = inp["spec"], inp["st"]
    stalker, player = spec["type"] == W.PT_STALKER, spec["type"] == W.PT_PLAYER
    d = inp["dark"]
    f = 0

    def on(name, cond):
        nonlocal f
        if cond:
            f |= FLAG[name]

    got = out["caught"] >= 0
    on("asleep", out["asleep"])
    on("cooldown", (not out["asleep"]) and st["cd"] - 1 > 0)
    on("wander", out["hunting"] and not out["has_target"])
    on("target", out["has_target"])
    on("catch", got)
    on("ranged_roll_miss", spec["ranged"] and out["hunting"] and bool(np.any(diag["catch_d"] <= spec["catch_r"]))
       and not got)
    on("twilight", (not spec["noct"]) and (not out["asleep"]) and 0.0 < d < 0.5)
    on("night_active", spec["noct"] and d >= 0.5)
    on("wall", out["wall"])
    on("dusk_exact", d == 0.5)
    v = np.sort(diag["perceived"][diag["vis"]])
    h = np.sort(diag["catch_d"][diag["hit"]])
    on("tie_exact", (len(v) >= 2 and v[1] == v[0]) or (len(h) >= 2 and h[1] == h[0]))
    if stalker:
        on("stalking", diag["stalking"])
        on("pounce_start", out["pounce_start"])
        on("pounce_dash", diag["dash"] and out["has_target"] and not out["pounce_start"])
        on("pounce_dash_blind", diag["dash"] and not out["has_target"])
        on("pounce_final_miss", diag["final"] and not got)
        on("pounce_catch", (diag["dash"] or diag["final"]) and got)
        on("exhaust", diag["exh0"] and post["ss"] == W.ST_EXHAUST)
        on("exhaust_end", diag["exh0"] and post["ss"] == W.ST_ROAM)
        on("sleep_reset", out["asleep"] and (st["ss"] != W.ST_ROAM or st["sl"] != 0))
    if player:
        pm, pl = diag["pm_motion"], diag["pl_motion"]
        on("p_wander", pm == W.PM_WANDER)
        on("p_stalk", pm == W.PM_STALK)
        on("p_charge_start", out["charge_start"])
        on("p_charge_dash", pm == W.PM_CHARGE and pl > 0 and not out["charge_start"])
        on("p_charge_final", pm == W.PM_CHARGE and pl <= 0)
        on("p_charge_catch", pm == W.PM_CHARGE and got)
        on("p_rest", pm == W.PM_REST and not out["new_mode"])
        on("p_rest_end", pm == W.PM_REST and out["new_mode"])
        on("p_mode_end", pm in (W.PM_WANDER, W.PM_STALK) and out["new_mode"])
    return f


def trim_prey(inp, out, diag) -> np.ndarray:
    """실을 초식 색인 (원래 순서). 표적·포획 반경 안 초식은 늘 싣고, 체감 거리가 가까운 순으로 채운다(모듈 docstring 3)."""
    per = diag["perceived"]
    n = len(per)
    must = set()
    if out["has_target"]:
        must.add(int(out["target"]))
    must |= set(np.flatnonzero(diag["catch_d"] <= inp["spec"]["catch_r"]).tolist())
    sel = set(must)
    for i in np.lexsort((np.arange(n), per)):
        if len(sel) >= max(MAX_PREY, len(must)):
            break
        if per[i] > KEEP_R and len(sel) >= K_NEAR:
            break
        sel.add(int(i))
    return np.array(sorted(sel), dtype=np.int64)


def make_case(c, rec, m, kind, label=-1, trim=True) -> dict:
    """기록 하나의 위협 m → 골든 사례 (초식 줄이기 + 참조 스텝 재확인).

    기대값은 world.py 가 낸 값이다(위치·heading·변위·정수 상태·잠·표적 유무·d_t·포획 여부·적용 속력). world.py 가 밖으로 내지 않는
    표적·포획 개체 색인·사냥·벽·시작 표시·새 모드는 참조 스텝 값이고, 참조 스텝이 world.py 와 같다는 확인(check_ref, 포획 합집합)을
    거친 값이다."""
    full = threat_inputs(rec, m)
    env = env_result(rec, m)
    post, out, diag = run_ref(c, full)
    check_ref(full, env, post, out, f"seed {rec['pre']['seed']} t {rec['pre']['t']} 위협 {m} (전체 초식)")
    idx = trim_prey(full, out, diag) if trim else np.arange(len(full["prey"]["x"]))
    inp = threat_inputs(rec, m, idx)
    post2, out2, diag2 = run_ref(c, inp)
    where = f"seed {rec['pre']['seed']} t {rec['pre']['t']} 위협 {m} (줄인 초식 {len(idx)})"
    check_ref(inp, env, post2, out2, where)
    if out2["caught"] >= 0 and int(idx[out2["caught"]]) != out["caught"]:
        raise SystemExit(f"줄인 초식에서 잡은 개체가 다르다 ({where})")
    if out2["has_target"] and int(idx[out2["target"]]) != out["target"]:
        raise SystemExit(f"줄인 초식에서 표적이 다르다 ({where})")
    o = dict(out2)
    o.update({k: env["out"][k] for k in ("asleep", "has_target", "d_t", "speed")})
    return dict(kind=kind, label=label, src=(int(rec["pre"]["seed"]), int(rec["pre"]["t"]), int(m)),
                key=type_key(rec, m), flags=flags_of(c, inp, env["post"], o, diag2),
                near=near_reasons(c, full, out, diag), inp=inp, post=env["post"], out=o)


# --------------------------------------------------------------------- #
# 롤아웃
# --------------------------------------------------------------------- #


def check_seeds(seeds) -> None:
    for s in seeds:
        for lo, hi in JUDGE_SEED_RANGES:
            if lo <= int(s) < hi:
                raise SystemExit(f"시드 {s} 는 판정 시드 범위 [{lo}, {hi}) 다 — 골든은 보정 시드(20000~)만 쓴다")


def collect_rollout(model, cfg, seed: int, steps: int) -> list:
    """보정 시드 하나를 R1b argmax 로 돌리며 위협 스텝을 모두 기록한다."""
    from env_v2.rollout import RepLearned

    W = _w()
    w = W.World(cfg, seeds=[seed])
    pol = RepLearned(model)
    pol.bind_world(w)
    rec = Recorder(w)
    for _ in range(steps):
        a = pol(w.observe())
        w.step(a)
    rec.detach()
    return rec.records


def validate_records(c, records) -> list:
    """모든 위협 스텝에서 참조 스텝 = world.py (전체 초식). 반환: 풀 항목 [(기록 번호, 위협, 종류 키, 표시, 문턱 근처 비트)]."""
    pool = []
    for ri, rec in enumerate(records):
        M = rec["pre"]["M"]
        union = set()
        for m in range(M):
            inp = threat_inputs(rec, m)
            env = env_result(rec, m)
            post, out, diag = run_ref(c, inp)
            check_ref(inp, env, post, out, f"seed {rec['pre']['seed']} t {rec['pre']['t']} 위협 {m}")
            if out["caught"] >= 0:
                union.add(out["caught"])
            pool.append((ri, m, type_key(rec, m), flags_of(c, inp, post, out, diag), near_reasons(c, inp, out, diag)))
        if sorted(union) != np.flatnonzero(rec["caught"]).tolist():
            raise SystemExit(f"seed {rec['pre']['seed']} t {rec['pre']['t']}: 참조 포획 합집합이 world.py caught 와 다르다")
    return pool


def find_windows(records, pool) -> list:
    """롤아웃 열 후보: (이름, 기록 번호 목록, 위협). 모든 스텝이 문턱 근처가 아니어야 한다."""
    by = {}
    for ri, m, key, f, near in pool:
        by.setdefault((records[ri]["pre"]["seed"], m), []).append((ri, key, f, near))
    out = []
    want = {"pounce_miss": 1, "pounce_catch": 1, "charge_cycle": 1, "catch_cooldown_chaser": 1,
            "catch_cooldown_ranged": 1, "dusk": 1, "dawn": 1}
    got = {k: 0 for k in want}

    def take(name, items, a, b, m):
        if got[name] >= want[name] or a < 0 or b > len(items):
            return False
        if any(items[i][3] for i in range(a, b)):
            return False
        out.append((name, [items[i][0] for i in range(a, b)], m))
        got[name] += 1
        return True

    for (seed, m), items in sorted(by.items()):
        key = items[0][1]
        fl = [it[2] for it in items]
        darks = [records[it[0]]["pre"]["dark"] for it in items]
        for i, f in enumerate(fl):
            if key == "stalker" and f & FLAG["pounce_start"]:
                for e in range(i, min(i + 60, len(fl))):
                    if fl[e] & FLAG["pounce_catch"]:
                        take("pounce_catch", items, i - 1, e + 7, m)
                        break
                    if fl[e] & FLAG["exhaust_end"]:
                        take("pounce_miss", items, i - 1, e + 2, m)
                        break
                    if fl[e] & FLAG["sleep_reset"]:
                        break
            if key == "player" and f & FLAG["p_charge_start"]:
                for e in range(i, min(i + 70, len(fl))):
                    if fl[e] & FLAG["p_rest_end"]:
                        take("charge_cycle", items, i - 1, e + 2, m)
                        break
            if key in ("chaser", "ranged") and f & FLAG["catch"]:
                take(f"catch_cooldown_{key}", items, i - 1, i + 7, m)
            if key != "player" and i >= 1 and darks[i] == 0.5 and not records[items[i][0]]["pre"]["noct"][m]:
                if darks[i - 1] < 0.5:
                    take("dusk", items, i - 2, i + 3, m)
                elif darks[i - 1] > 0.5:
                    take("dawn", items, i - 2, i + 3, m)
    return out


# --------------------------------------------------------------------- #
# 무대 (손으로 놓은 세계 — 같은 world.py 함수를 부른다)
# --------------------------------------------------------------------- #

# 무대 시각 (T 900, o 0, τ 45): 낮 d 0, 해 질 녘 전환 d 0.5, 그 한 스텝 전 d 0.48889, 박명 d 0.27778, 해 뜰 녘 전환 0.5, 밤 1
CLOCK = dict(day=100, dusk=450, dusk_before=449, twilight=20, dawn=0, night=600)
STAGE_PERIOD, STAGE_OFFSET, STAGE_TW = 900, 0, 45
STAGE_SIZE = 80.0
STAGE_MULT = 0.8                       # 세계 속도 배수 (학습 범위 [0.6, 0.95] 안)
UP = 2.0 ** -12                        # 문턱 '바로 위' (2^-12 ≈ 2.4e-4 > 제외 폭 1e-4, 2 진수로 정확)


class Stage:
    """무대 세계: 실제 World 를 만들고 위협·초식·은신처·시각을 덮어쓴 뒤 같은 `_step_predators_v3` 를 부른다(Recorder 로 기록)."""

    def __init__(self, cfg, threats: list, size: float = STAGE_SIZE):
        W = _w()
        self.cfg = cfg
        w = self.w = W.World(cfg, seeds=[STAGE_SEED])
        th = [t for t in threats if t["type"] != W.PT_PLAYER] + [t for t in threats if t["type"] == W.PT_PLAYER]
        M, Mb = len(th), sum(t["type"] != W.PT_PLAYER for t in th)
        w.size = float(size)
        w.M, w.M_base = M, Mb
        w.player_present = M > Mb
        w.pred_pos = np.array([t["pos"] for t in th], dtype=np.float64).reshape(M, 2)
        w.pred_head = np.array([t["head"] for t in th], dtype=np.float64).reshape(M, 2)
        w.pred_type = np.array([t["type"] for t in th], dtype=np.int8)
        w.pred_is_player = w.pred_type == W.PT_PLAYER
        w.pred_ranged = np.array([t.get("ranged", False) for t in th], dtype=bool)
        w._pred_ranged_v1 = w.pred_ranged.copy()
        w.pred_speed_mult = STAGE_MULT
        base = cfg.herb_speed * STAGE_MULT
        w.pred_speed = np.where(w.pred_is_player, 0.0,
                                np.where(w.pred_ranged, base * cfg.pred_ranged_speed_mult, base)).astype(np.float64)
        w.pred_catch_r = np.where(w.pred_is_player, w._th["player_catch_r"],
                                  np.where(w.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r))
        w.pred_cd = np.array([t.get("cd", 0) for t in th], dtype=np.int32)
        w.stalk_state = np.array([t.get("ss", 0) for t in th], dtype=np.int8)
        w.stalk_left = np.array([t.get("sl", 0) for t in th], dtype=np.int64)
        w.player_mode = np.array([t.get("pm", 0) for t in th], dtype=np.int8)
        w.player_left = np.array([t.get("pl", 0) for t in th], dtype=np.int64)
        w.pred_nocturnal = np.array([t.get("noct", False) or t["type"] == W.PT_PLAYER for t in th], dtype=bool)
        w.pred_asleep = np.zeros(M, dtype=bool)
        w._pred_speed_mult = np.ones(M)
        w.pred_vel = np.zeros((M, 2))
        w.day_fixed = False
        w.dn_period, w.dn_offset, w.dn_tw = STAGE_PERIOD, STAGE_OFFSET, STAGE_TW
        w.seed = -1
        self.rec = Recorder(w)

    def step(self, prey: list, t: int, turns, covers=(), rolls=None, mode=(0.5, 0.5)):
        """초식(dict: pos·beh·arrived)·은신처((cx, cy, r) 목록)·시각 t 를 놓고 위협 스텝 하나. 반환: 기록."""
        from env_v2 import repertoire as rep

        w = self.w
        n = len(prey)
        w.N = n
        w.pos = np.array([p["pos"] for p in prey], dtype=np.float64).reshape(n, 2)
        beh = np.array([p.get("beh", rep.GRAZE) for p in prey], dtype=np.int8)
        arrived = np.array([p.get("arrived", False) for p in prey], dtype=bool)
        w._rs.behavior, w._rs.arrived = beh, arrived
        crouch = (beh == rep.HIDE) & arrived
        w._rep_still = (beh == rep.FREEZE) | (beh == rep.SLEEP) | crouch
        w._rep_cover = rep.cover_mult(w._rp, beh, crouch)
        w.cov_c = np.array([cv[:2] for cv in covers], dtype=np.float64).reshape(-1, 2)
        w.cov_r = np.array([cv[2] for cv in covers], dtype=np.float64).reshape(-1)
        w.t = int(t)
        w._daynight_update()
        Mb = w.M_base
        w.rng = _Script(turns=list(turns)[:Mb], randoms=[np.asarray(rolls, dtype=np.float64).reshape(Mb, n)]
                        if rolls is not None else [])
        w._feature_rngs[("threats", 3)] = _Script(turns=list(turns)[Mb:])
        w._feature_rngs[("threats", 2)] = _Script(randoms=[np.asarray(mode, dtype=np.float64)])
        w._step_predators_v3()
        return self.rec.records[-1]


def _threat(type_, **kw) -> dict:
    d = dict(type=type_, pos=(40.0, 40.0), head=(1.0, 0.0))
    d.update(kw)
    return d


def _prey(x, y, **kw) -> dict:
    d = dict(pos=(float(x), float(y)))
    d.update(kw)
    return d


def edge_specs() -> list:
    """끝 사례 (이름, 위협, 초식, 은신처, 시각, 선회, 원거리 난수, 모드 난수). 위협은 (40, 40), heading +x 가 기본이다."""
    W = _w()
    from env_v2 import repertoire as rep

    C, S, P = W.PT_CHASER, W.PT_STALKER, W.PT_PLAYER
    G, F, H, Z, SL = rep.GRAZE, rep.FLEE, rep.HIDE, rep.FREEZE, rep.SLEEP
    day, dusk, dawn, night = CLOCK["day"], CLOCK["dusk"], CLOCK["dawn"], CLOCK["night"]
    r2 = math.sqrt(0.5)
    e = []

    def add(name, threat, prey, covers=(), t=day, turn=0.05, rolls=None, mode=(0.5, 0.5)):
        e.append(dict(name=name, threat=threat, prey=prey, covers=covers, t=t, turn=turn, rolls=rolls, mode=mode))

    # 잠행형 돌진 시작 문턱 (체감 거리 6, 정확히 같음 → 시작)
    add("stalk_start_exact", _threat(S), [_prey(46, 40)])
    add("stalk_above", _threat(S), [_prey(46 + UP, 40)])
    add("stalk_start_cover_graze", _threat(S), [_prey(44, 40, beh=G)], covers=[(44.0, 40.0, 2.0)])
    add("stalk_freeze_far", _threat(S), [_prey(44, 40, beh=Z)])              # 실거리 4 × 1.8 = 7.2 > 6 → 잠행
    # 플레이어 돌진 시작 문턱
    add("charge_start_exact", _threat(P, pm=W.PM_STALK, pl=100), [_prey(46, 40)])
    add("charge_above", _threat(P, pm=W.PM_STALK, pl=100), [_prey(46 + UP, 40)])
    # 포획 반경
    add("catch_exact", _threat(C), [_prey(41, 40)])
    add("catch_above", _threat(C), [_prey(41 + UP, 40)])
    add("ranged_exact_pass", _threat(C, ranged=True), [_prey(43, 40)], rolls=[[0.0199]])
    add("ranged_roll_equal_p", _threat(C, ranged=True), [_prey(43, 40)], rolls=[[0.02]])
    add("ranged_above_roll0", _threat(C, ranged=True), [_prey(43 + UP, 40)], rolls=[[0.0]])
    # 위협 시야 반경·시야각
    add("view_exact", _threat(C), [_prey(54, 40)])
    add("view_above", _threat(C), [_prey(54 + UP, 40)])
    add("fov_behind", _threat(C), [_prey(37, 40), _prey(45, 40)])
    add("fov_side_out", _threat(C), [_prey(40, 45)])                          # 90° 옆 → 안 보임
    # 행동별 은신 배수·정지 탐지
    add("crouch_cover_catch_exact", _threat(C), [_prey(40.25, 40, beh=H, arrived=True)], covers=[(41.0, 40.0, 2.0)])
    add("crouch_cover_safe", _threat(C), [_prey(40.375, 40, beh=H, arrived=True)], covers=[(41.0, 40.0, 2.0)])
    add("crouch_outside", _threat(C), [_prey(40.5, 40, beh=H, arrived=True)])
    add("hide_travel_cover", _threat(C), [_prey(40.875, 40, beh=H)], covers=[(41.0, 40.0, 2.0)])
    add("freeze_catch", _threat(C), [_prey(40.75, 40, beh=Z)])
    add("sleep_cover_catch", _threat(C), [_prey(40.375, 40, beh=SL)], covers=[(41.0, 40.0, 2.0)])
    add("sleep_cover_safe", _threat(C), [_prey(40.5, 40, beh=SL)], covers=[(41.0, 40.0, 2.0)])
    add("sleep_outside", _threat(C), [_prey(40.875, 40, beh=SL)])
    add("flee_cover_catch", _threat(C), [_prey(40.875, 40, beh=F)], covers=[(41.0, 40.0, 2.0)])
    add("graze_cover_safe", _threat(C), [_prey(40.75, 40, beh=G)], covers=[(41.0, 40.0, 2.0)])
    add("freeze_vs_graze_target", _threat(C), [_prey(45, 40, beh=Z), _prey(47, 40, beh=G)])   # 9 > 7 → 뒤 개체
    # 동점 규칙 (낮은 색인)
    add("tie_target", _threat(C, head=(r2, r2)), [_prey(43, 40), _prey(40, 43)])
    add("tie_target_swapped", _threat(C, head=(r2, r2)), [_prey(40, 43), _prey(43, 40)])
    add("tie_catch", _threat(C, head=(r2, r2)), [_prey(40.5, 40), _prey(40, 40.5)])
    add("player_tie_target", _threat(P, pm=W.PM_STALK, pl=50), [_prey(32, 40), _prey(40, 48)])     # 맵 전체를 본다: 뒤쪽도
    add("player_tie_catch", _threat(P, pm=W.PM_WANDER, pl=50), [_prey(40, 39.5), _prey(39.5, 40)])
    # 잠행형 상태 기계
    add("exhaust_end", _threat(S, ss=W.ST_EXHAUST, sl=1), [_prey(40.5, 40)])
    add("exhaust_mid", _threat(S, ss=W.ST_EXHAUST, sl=30), [_prey(40.5, 40)])
    add("pounce_final_miss", _threat(S, ss=W.ST_POUNCE, sl=0), [_prey(45, 40)])
    add("pounce_final_catch", _threat(S, ss=W.ST_POUNCE, sl=0), [_prey(40.5, 40)])
    add("pounce_dash_blind", _threat(S, ss=W.ST_POUNCE, sl=5), [_prey(36, 40)])
    add("pounce_dash_catch", _threat(S, ss=W.ST_POUNCE, sl=3), [_prey(40.5, 40)])
    add("stalker_roam_cooldown", _threat(S, cd=3), [_prey(44, 40)])
    # 낮밤 (잠·박명)
    add("dusk_asleep_chaser", _threat(C, cd=3), [_prey(40.5, 40)], t=dusk)
    add("dawn_asleep_chaser", _threat(C), [_prey(40.5, 40)], t=dawn)
    add("dusk_before_twilight", _threat(C), [_prey(43, 40)], t=CLOCK["dusk_before"])
    add("twilight_wander", _threat(C), [_prey(20, 40)], t=CLOCK["twilight"])
    add("nocturnal_night", _threat(C, noct=True), [_prey(43, 40)], t=night)
    add("nocturnal_dusk", _threat(C, noct=True), [_prey(43, 40)], t=dusk)
    add("ranged_nocturnal_night", _threat(C, ranged=True, noct=True), [_prey(42.5, 40)], t=night, rolls=[[0.01]])
    add("ranged_asleep_dusk", _threat(C, ranged=True), [_prey(42.5, 40)], t=dusk, rolls=[[0.01]])
    add("stalker_sleep_reset_pounce", _threat(S, ss=W.ST_POUNCE, sl=7), [_prey(41.5, 40)], t=night)
    add("stalker_sleep_reset_exhaust", _threat(S, ss=W.ST_EXHAUST, sl=12), [_prey(41.5, 40)], t=dusk)
    add("player_night", _threat(P, pm=W.PM_STALK, pl=50), [_prey(48, 40)], t=night)
    # 벽 (world.py 는 초식이 없는 세계를 다루지 못한다(argmin) — 보이지 않는 먼 초식 하나를 둔다)
    add("wall_x", _threat(C, pos=(79.875, 40.0)), [_prey(5, 75)], turn=0.0)
    add("wall_corner", _threat(C, pos=(0.125, 0.125), head=(-0.6, -0.8)), [_prey(75, 75)], turn=0.0)
    add("wall_chase", _threat(C, pos=(79.875, 40.0)), [_prey(80, 40.25)])
    # 플레이어
    add("player_far", _threat(P, pos=(10.0, 10.0), pm=W.PM_STALK, pl=50), [_prey(70, 70)])
    add("player_rest_end_stalk", _threat(P, pm=W.PM_REST, pl=1), [_prey(40.5, 40)], mode=(0.3, 0.999))
    add("player_rest_end_wander", _threat(P, pm=W.PM_REST, pl=1), [_prey(40.5, 40)], mode=(0.5, 0.0))
    add("player_mode_end", _threat(P, pm=W.PM_STALK, pl=1), [_prey(50, 40)], mode=(0.0, 0.5))
    add("player_wander_end", _threat(P, pm=W.PM_WANDER, pl=1), [_prey(50, 40)], mode=(0.75, 0.25))
    add("player_charge_final", _threat(P, pm=W.PM_CHARGE, pl=0), [_prey(45, 40)])
    add("player_charge_catch", _threat(P, pm=W.PM_CHARGE, pl=7), [_prey(40.5, 40)])
    add("player_charge_cooldown", _threat(P, pm=W.PM_CHARGE, pl=7, cd=3), [_prey(45, 40)])
    add("player_wander_catch", _threat(P, pm=W.PM_WANDER, pl=50), [_prey(40.5, 40)])
    add("player_rest_no_catch", _threat(P, pm=W.PM_REST, pl=10), [_prey(40.5, 40)])
    # 쿨다운 1·2 (1 → 이번 스텝 0 이라 잡는다, 2 → 1 이라 못 잡는다)
    add("chaser_cd1", _threat(C, cd=1), [_prey(40.5, 40)])
    add("chaser_cd2", _threat(C, cd=2), [_prey(40.5, 40)])
    add("player_cd1", _threat(P, pm=W.PM_WANDER, pl=50, cd=1), [_prey(40.5, 40)])
    add("player_cd2", _threat(P, pm=W.PM_WANDER, pl=50, cd=2), [_prey(40.5, 40)])
    # 같은 자리 (거리 0): 추격형은 시야각 판정이 0 이라 못 보지만 포획 거리 0 이라 잡는다. 플레이어는 표적 → move 0 → heading 0
    add("zero_dist_chaser", _threat(C), [_prey(40, 40)])
    add("zero_dist_player", _threat(P, pm=W.PM_STALK, pl=50), [_prey(40, 40)])
    # 선회 끝값
    add("wander_turn_max", _threat(C), [_prey(5, 75)], turn=0.15)
    add("wander_turn_min", _threat(C), [_prey(5, 75)], turn=-0.15)
    return e


def run_edges(cfg, c) -> list:
    cases = []
    for li, e in enumerate(edge_specs()):
        stg = Stage(cfg, [e["threat"]])
        turns = [e["turn"]]
        rec = stg.step(e["prey"], e["t"], turns, covers=e["covers"], rolls=e["rolls"], mode=e["mode"])
        stg.rec.detach()
        case = make_case(c, rec, 0, KIND_EDGE, label=li, trim=False)
        case["src"] = (-1, li, 0)
        cases.append(case)
    return cases


def _turn_k(k: int) -> float:
    """무대 열 선회 값 (결정적, [−0.15, 0.15] 안)."""
    return 0.15 * (((k * 7) % 11) - 5) / 5.0


def stage_sequences(cfg, c) -> list:
    """무대 열: (이름, 사례 목록). 초식은 매 스텝 위협의 지금 위치·heading 앞 r 에 놓는다."""
    W = _w()
    from env_v2 import repertoire as rep

    def ahead(stg, r, beh=rep.GRAZE):
        q, h = stg.w.pred_pos[0], stg.w.pred_head[0]
        return [_prey(q[0] + r * h[0], q[1] + r * h[1], beh=beh)]

    seqs = []

    def run(name, threat, plan, t0=CLOCK["day"], dt=0):
        stg = Stage(cfg, [threat])
        cases = []
        for k, (r, mode) in enumerate(plan):
            prey = ahead(stg, r)
            rec = stg.step(prey, t0 + k * dt, [_turn_k(k)], mode=mode)
            case = make_case(c, rec, 0, KIND_STAGE_SEQ, trim=False)
            case["src"] = (-2, len(seqs), k)
            cases.append(case)
        stg.rec.detach()
        check_chain(name, cases)
        seqs.append((name, cases))

    # 쿨다운 5 의 뜻: 0 스텝에 잡음 → 1~4 사냥 안 함 → 5 스텝에 다시 잡음 → 6 스텝 다시 쉼
    run("chaser_cooldown5", _threat(W.PT_CHASER), [(0.5, None)] * 7)
    # 잠행형 한 주기: 잠행 → 돌진 시작 → 돌진 12 → 마지막 판정 놓침 → 탈진 30 → ROAM → 다시 시작
    run("stalker_cycle", _threat(W.PT_STALKER), [(8.0, None)] + [(5.0, None)] * 44)
    # 플레이어 돌진 한 주기: 잠행 → 돌진 시작 → 돌진 20 → 멈춘 판정 → 휴식 30 → 새 모드 (u0 0.25 → 잠행, 길이 200 + 120)
    run("player_cycle", _threat(W.PT_PLAYER, pm=W.PM_STALK, pl=300), [(8.0, (0.25, 0.6))] + [(5.0, (0.25, 0.6))] * 52)
    # 해 질 녘: 주행성 추격형이 t 447~452 (d 0.467 → 0.5 잠 → 0.522)
    run("dusk_chaser", _threat(W.PT_CHASER), [(3.0, None)] * 6, t0=CLOCK["dusk"] - 3, dt=1)
    # 해 뜰 녘: t 897~902 (밤 → 0.5 잠 → 0.489 깨어 박명)
    run("dawn_stalker", _threat(W.PT_STALKER, ss=W.ST_EXHAUST, sl=20), [(3.0, None)] * 6, t0=STAGE_PERIOD - 3, dt=1)
    return seqs


# --------------------------------------------------------------------- #
# 골든 모으기
# --------------------------------------------------------------------- #


def build_golden(model, cfg, seeds, steps: int) -> dict:
    W = _w()
    check_seeds(seeds)
    c = cfg_constants(cfg)
    records = []
    for s in seeds:
        records += collect_rollout(model, cfg, int(s), steps)
    pool = validate_records(c, records)
    stats = dict(seeds=[int(s) for s in seeds], steps=int(steps), pool=len(pool), records=len(records))

    key_arr = np.array([p[2] for p in pool])
    flag_arr = np.array([p[3] for p in pool], dtype=np.int64)
    near_arr = np.array([p[4] for p in pool], dtype=np.int64)
    stats["pool_by_type"] = {k: int((key_arr == k).sum()) for k in TYPE_KEYS}
    stats["near_by_reason"] = {r: int(((near_arr >> i) & 1).sum()) for i, r in enumerate(EX_REASONS)}
    stats["near_by_type"] = {k: int(((near_arr != 0) & (key_arr == k)).sum()) for k in TYPE_KEYS}
    stats["near_total"] = int((near_arr != 0).sum())
    stats["pool_flags"] = {k: {f: int(((flag_arr & FLAG[f]) != 0)[key_arr == k].sum()) for f in TYPE_FLAGS[k]}
                           for k in TYPE_KEYS}

    # 본 묶음: 종류 × 표시마다 PER_FLAG 개 (문턱 근처 제외)
    rng = np.random.default_rng(SELECT_SEED)
    chosen = set()
    for k in TYPE_KEYS:
        for f in TYPE_FLAGS[k]:
            idx = np.flatnonzero((key_arr == k) & ((flag_arr & FLAG[f]) != 0) & (near_arr == 0))
            if len(idx) > PER_FLAG:
                idx = np.sort(rng.choice(idx, size=PER_FLAG, replace=False))
            chosen |= set(int(i) for i in idx)
    main = [make_case(c, records[pool[i][0]], pool[i][1], KIND_MAIN) for i in sorted(chosen)]
    for cs in main:
        if cs["near"]:
            raise SystemExit("본 묶음에 문턱 근처 사례가 들어갔다")

    # 문턱 근처 묶음 (보고만): 이유마다 고르게
    near_idx = []
    for i, r in enumerate(EX_REASONS):
        idx = np.flatnonzero((near_arr >> i) & 1)
        if len(idx):
            near_idx += np.sort(rng.choice(idx, size=min(2, len(idx)), replace=False)).tolist()
    near_idx = sorted(set(near_idx))[:N_NEAR_GROUP]
    near = [make_case(c, records[pool[i][0]], pool[i][1], KIND_NEAR) for i in near_idx]

    # 롤아웃 열
    seqs = []
    for name, ris, m in find_windows(records, pool):
        cases = [make_case(c, records[ri], m, KIND_SEQ) for ri in ris]
        check_chain(name, cases)
        seqs.append((name, KIND_SEQ, cases))
    stats["rollout_seqs"] = [name for name, _, _ in seqs]

    edges = run_edges(cfg, c)
    for name, cases in stage_sequences(cfg, c):
        seqs.append((name, KIND_STAGE_SEQ, cases))
    stats["edge_names"] = [e["name"] for e in edge_specs()]
    return dict(c=c, main=main, near=near, edges=edges, seqs=seqs, stats=stats)


# --------------------------------------------------------------------- #
# 헤더 쓰기
# --------------------------------------------------------------------- #


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"헤더에 유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s or "inf" in s) else s + ".0"


def c_array(ctype: str, name: str, arr, per_line: int, fmt, comment: str = "") -> str:
    flat = list(np.asarray(arr).reshape(-1)) if not isinstance(arr, list) else arr
    if len(flat) == 0:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    head = f"\tinline constexpr {ctype} {name}[{len(flat)}] = {{" + (f"   // {comment}" if comment else "")
    lines = [head]
    for i in range(0, len(flat), per_line):
        chunk = ", ".join(fmt(v) for v in flat[i:i + per_line])
        lines.append("\t\t" + chunk + ("," if i + per_line < len(flat) else ""))
    lines.append("\t};")
    return "\n".join(lines)


def _i(v) -> str:
    return str(int(v))


def flatten(g: dict) -> dict:
    """사례 목록 → 헤더 배열. 순서: 본, 끝 사례, 열(롤아웃·무대, 열마다 이어서), 문턱 근처."""
    cases = list(g["main"]) + list(g["edges"])
    seq_tab = []
    for name, kind, cs in g["seqs"]:
        seq_tab.append((name, kind, len(cases), len(cs)))
        cases += cs
    near_begin = len(cases)
    cases += list(g["near"])
    A = {k: [] for k in ("kind", "src", "label", "flags", "near", "type", "ranged", "noct", "base", "catch_r", "mult",
                         "pre_pos", "pre_head", "pre_int", "dark", "size", "turn", "mode_u", "clock", "pbeg", "pcnt",
                         "post_pos", "post_head", "post_vel", "post_int", "out_bits", "target", "d_t", "caught", "speed")}
    P = {k: [] for k in ("pos", "beh", "arrived", "in_cover", "roll", "slot")}
    for cs in cases:
        inp, post, out = cs["inp"], cs["post"], cs["out"]
        sp, st, pr = inp["spec"], inp["st"], inp["prey"]
        A["kind"].append(cs["kind"])
        A["src"] += list(cs["src"])
        A["label"].append(cs["label"])
        A["flags"].append(cs["flags"])
        A["near"].append(cs["near"])
        A["type"].append(sp["type"])
        A["ranged"].append(int(sp["ranged"]))
        A["noct"].append(int(sp["noct"]))
        A["base"].append(sp["base_speed"])
        A["catch_r"].append(sp["catch_r"])
        A["mult"].append(sp["mult"])
        A["pre_pos"] += list(st["pos"])
        A["pre_head"] += list(st["head"])
        A["pre_int"] += [st[k] for k in INT_COLS]
        A["dark"].append(inp["dark"])
        A["size"].append(inp["size"])
        A["turn"].append(inp["turn"])
        A["mode_u"] += list(inp["mode_u"])
        A["clock"] += list(inp["clock"])
        A["pbeg"].append(len(P["slot"]))
        A["pcnt"].append(len(pr["x"]))
        for i in range(len(pr["x"])):
            P["pos"] += [float(pr["x"][i]), float(pr["y"][i])]
            P["beh"].append(int(pr["beh"][i]))
            P["arrived"].append(int(pr["arrived"][i]))
            P["in_cover"].append(int(pr["in_cover"][i]))
            P["roll"].append(float(inp["roll"][i]) if inp["roll"] is not None else NO_ROLL)
            P["slot"].append(int(pr["slot"][i]))
        A["post_pos"] += list(post["pos"])
        A["post_head"] += list(post["head"])
        A["post_vel"] += list(post["vel"])
        A["post_int"] += [post[k] for k in INT_COLS]
        A["out_bits"].append(sum(1 << i for i, b in enumerate(OUT_BITS)
                                 if (out["new_mode"] if b == "new_mode" else out[b])))
        A["target"].append(out["target"])
        A["d_t"].append(out["d_t"])
        A["caught"].append(out["caught"])
        A["speed"].append(out["speed"])
    return dict(A=A, P=P, cases=cases, seq_tab=seq_tab, near_begin=near_begin)


def count_table(cases, kinds) -> dict:
    """(종류 키, 표시) → 사례 수 (주어진 사례 종류만)."""
    out = {k: {f: 0 for f in TYPE_FLAGS[k]} for k in TYPE_KEYS}
    for cs in cases:
        if cs["kind"] in kinds:
            for f in TYPE_FLAGS[cs["key"]]:
                if cs["flags"] & FLAG[f]:
                    out[cs["key"]][f] += 1
    return out


def write_header(path: Path, g: dict, meta: dict) -> None:
    """ThreatGoldenVectorsV3.h — 위협 모델 골든 (모듈 docstring)."""
    c, s = g["c"], g["stats"]
    fl = flatten(g)
    A, P, cases = fl["A"], fl["P"], fl["cases"]
    n = len(cases)
    kinds = np.bincount(np.array(A["kind"]), minlength=len(KIND_NAMES))
    edge_names = s["edge_names"]
    single = count_table(cases, (KIND_MAIN,))
    seqc = count_table(cases, (KIND_SEQ, KIND_STAGE_SEQ))
    edgec = count_table(cases, (KIND_EDGE,))

    lines = []
    for k in TYPE_KEYS:
        n_k = sum(1 for cs in cases if cs["key"] == k and cs["kind"] == KIND_MAIN)
        parts = [f"{f} {single[k][f]}/{seqc[k][f]}/{edgec[k][f]}" for f in TYPE_FLAGS[k]]
        lines.append(f"//   {k:8s} 본 {n_k}개 (풀 {s['pool_by_type'][k]}, 문턱 근처로 뺀 것 {s['near_by_type'][k]})")
        for i in range(0, len(parts), 5):
            lines.append("//     " + ", ".join(parts[i:i + 5]))
    type_table = "\n".join(lines)
    reasons = ", ".join(f"{r} {s['near_by_reason'][r]}" for r in EX_REASONS)
    seq_lines = "\n".join(f"//   {i:2d} {name:24s} {KIND_NAMES[kind]:6s} 사례 {beg}~{beg + ln - 1} ({ln}스텝)"
                          for i, (name, kind, beg, ln) in enumerate(fl["seq_tab"]))
    cfg_lines = []
    for k, v in c.items():
        if isinstance(v, bool):
            cfg_lines.append(f"\tinline constexpr bool kCfg{k[1:] if k.startswith('b') else k} = {'true' if v else 'false'};")
        elif isinstance(v, tuple):
            ct = "double" if isinstance(v[0], float) else "std::int32_t"
            fmt = d_lit if ct == "double" else _i
            cfg_lines.append(f"\tinline constexpr {ct} kCfg{k}[{len(v)}] = {{{', '.join(fmt(x) for x in v)}}};")
        elif isinstance(v, float):
            cfg_lines.append(f"\tinline constexpr double kCfg{k} = {d_lit(v)};")
        else:
            cfg_lines.append(f"\tinline constexpr std::int32_t kCfg{k} = {int(v)};")
    cfg_block = "\n".join(cfg_lines)

    body = f"""// 자동 생성. 수정 금지.
// 생성: herbivore_rl/export_golden_v3_threat.py — v3 위협 모델 골든 (EcoThreatModel.h EcoThreatV3::Step 대조, 계약 G7)
// world:  {meta["world_config"]}  (config_digest {meta["world_digest"]})
// deer:   {meta["model"]}  (sha256 {meta["model_sha256"]}) argmax — env_v2/rollout.py RepLearned
// seeds:  보정 시드 {" ".join(map(str, s["seeds"]))} x {s["steps"]}스텝 (판정 시드는 쓰지 않는다), 위협 스텝 풀 {s["pool"]}개
//
// 사례 kCaseCount = {n}: 본 {kinds[KIND_MAIN]}, 끝 사례 {kinds[KIND_EDGE]}, 롤아웃 열 {kinds[KIND_SEQ]}, 무대 열 {kinds[KIND_STAGE_SEQ]}, \
문턱 근처(보고만) {kinds[KIND_NEAR]}
//   한 사례 = 위협 하나의 결정 스텝 하나: 입력(위협 성질·상태, 초식 이동 뒤 위치·행동·HIDE 도착·은신처 안, 원거리 판정 난수,
//   어둠 d·시각, 맵 크기, 배회 선회, 플레이어 새 모드 난수) -> 기대(위협 위치·heading·변위·쿨다운·잠행 상태·남은·플레이어 모드·남은,
//   잠·사냥·표적·표적 체감 거리·포획·적용 속력·벽·돌진 시작·새 모드)
//   초식은 표적·포획 후보 + 체감 거리 <= {KEEP_R:g} 를 가까운 순으로 {MAX_PREY}마리까지(적어도 {K_NEAR}마리)로 줄였다. 원래 색인 순서다
//
// 위협 종류별 표시 사례 수 (본/열/끝):
{type_table}
//
// 문턱 근처 제외 (풀 전체, 이유 겹침 있음): 합계 {s["near_total"]} — {reasons}
//   |d - r| < {EX_DIST:g} (시야 14·포획·돌진 6), |cos - cos 75| < {EX_COS:g}, 표적·포획 1·2위 차 0 < 차 < {EX_TIE:g},
//   벽 0 < |x - 0 또는 size| < {EX_WALL:g}. 구조상 정확히 같은 값(d = 0.5, 벽에 붙은 축 이동 0, 같은 자리 동점)은 빼지 않는다
//
// 열 kSeqCount = {len(fl["seq_tab"])} (C++ 은 첫 스텝만 골든 입력 상태를 쓰고, 그 뒤는 자기 출력 상태를 이어 쓴다):
{seq_lines}
//
// 끝 사례 이름 kEdgeNames (무대 세계 — 같은 world.py 함수가 계산했다. 문턱과 정확히 같은 2 진수 거리를 쓴다)
// 허용: 실수 |C++ - Python| <= kFloatTolerance, 정수·열거·판정은 정확히 같다. 문턱 근처 묶음은 보고만 한다
#pragma once

#include <cstdint>

namespace EcoThreatV3::Golden
{{
	inline constexpr double kFloatTolerance = {d_lit(FLOAT_TOL)};
	inline constexpr double kNoRoll = {d_lit(NO_ROLL)};   // 원거리 판정 난수가 없는 칸 (원거리형이 아니다)

	// 사례 종류
	inline constexpr std::uint8_t kKindMain = {KIND_MAIN};        // 롤아웃 한 스텝
	inline constexpr std::uint8_t kKindEdge = {KIND_EDGE};        // 무대 끝 사례 한 스텝
	inline constexpr std::uint8_t kKindSeq = {KIND_SEQ};          // 롤아웃 열의 한 스텝
	inline constexpr std::uint8_t kKindStageSeq = {KIND_STAGE_SEQ};   // 무대 열의 한 스텝
	inline constexpr std::uint8_t kKindNear = {KIND_NEAR};        // 문턱 근처 (보고만)

	// 결과 비트 (kOutBits)
{chr(10).join(f"	inline constexpr std::uint8_t kOut{''.join(p.capitalize() for p in b.split('_'))} = {1 << i};" for i, b in enumerate(OUT_BITS))}

	// ---- 학습 세계 설정 (EcoThreatModel.h FThreatConfig 기본값과 정확히 같아야 한다) ----
{cfg_block}

	// ---- 표시·이름 ----
	inline constexpr std::int32_t kFlagCount = {len(FLAG_NAMES)};
	inline constexpr const char* kFlagNames[kFlagCount] = {{{", ".join(f'"{x}"' for x in FLAG_NAMES)}}};
	inline constexpr std::int32_t kEdgeCount = {len(edge_names)};
	inline constexpr const char* kEdgeNames[kEdgeCount] = {{
		{(","+chr(10)+chr(9)+chr(9)).join(f'"{x}"' for x in edge_names)}
	}};
	inline constexpr std::int32_t kSeqCount = {len(fl["seq_tab"])};
	inline constexpr const char* kSeqNames[kSeqCount] = {{{", ".join(f'"{x[0]}"' for x in fl["seq_tab"])}}};
{c_array("std::int32_t", "kSeqBegin", [x[2] for x in fl["seq_tab"]], 16, _i)}
{c_array("std::int32_t", "kSeqLength", [x[3] for x in fl["seq_tab"]], 16, _i)}

	// ---- 사례 ----
	inline constexpr std::int32_t kCaseCount = {n};
{c_array("std::uint8_t", "kCaseKind", A["kind"], 40, _i, comment="[n] kKind*")}
{c_array("std::int32_t", "kCaseSource", A["src"], 12, _i, comment="[n*3] 롤아웃: 시드, 스텝 t, 위협 색인 / 끝: -1, 이름 번호, 0 / 무대 열: -2, 열 번호, 스텝")}
{c_array("std::int32_t", "kCaseEdge", A["label"], 24, _i, comment="[n] kEdgeNames 번호 (끝 사례가 아니면 -1)")}
{c_array("std::uint32_t", "kCaseFlags", A["flags"], 12, _i, comment="[n] 상태·전이 표시 비트 (kFlagNames)")}
{c_array("std::uint8_t", "kCaseNear", A["near"], 40, _i, comment="[n] 문턱 근처 이유 비트 (본·롤아웃 열은 0. 끝 사례는 일부러 문턱과 정확히 같게 둔 비교가 표시된다)")}
	// 위협 성질 (FThreatSpec)
{c_array("std::uint8_t", "kSpecType", A["type"], 40, _i, comment="[n] EThreatType")}
{c_array("std::uint8_t", "kSpecRanged", A["ranged"], 40, _i)}
{c_array("std::uint8_t", "kSpecNocturnal", A["noct"], 40, _i)}
{c_array("double", "kSpecBaseSpeed", A["base"], 6, d_lit)}
{c_array("double", "kSpecCatchR", A["catch_r"], 8, d_lit)}
{c_array("double", "kSpecSpeedMult", A["mult"], 6, d_lit, comment="[n] 세계 pred_speed_mult (MakeChaserSpec 확인용)")}
	// 스텝 전 위협 상태
{c_array("double", "kPrePos", A["pre_pos"], 6, d_lit, comment="[n*2]")}
{c_array("double", "kPreHead", A["pre_head"], 6, d_lit, comment="[n*2]")}
{c_array("std::int32_t", "kPreInt", A["pre_int"], 15, _i, comment="[n*5] Cooldown, StalkState, StalkLeft, PlayerMode, PlayerLeft")}
	// 세계 입력
{c_array("double", "kDark", A["dark"], 6, d_lit, comment="[n] d(t)")}
{c_array("std::int32_t", "kClock", A["clock"], 16, _i, comment="[n*4] t, 하루 길이 T, 시작 위상 o, 박명 폭 τ (DayNightDark 확인용)")}
{c_array("double", "kWorldSize", A["size"], 6, d_lit)}
{c_array("double", "kTurn", A["turn"], 6, d_lit, comment="[n] 배회 선회 (파이썬이 뽑은 값)")}
{c_array("double", "kModeU", A["mode_u"], 6, d_lit, comment="[n*2] 플레이어 새 모드 난수 (새 모드를 고른 사례만 0 이 아닐 수 있다)")}
{c_array("std::int32_t", "kPreyBegin", A["pbeg"], 16, _i)}
{c_array("std::int32_t", "kPreyCount", A["pcnt"], 24, _i)}
	// 초식 (kPreyBegin[n] 부터 kPreyCount[n] 개)
	inline constexpr std::int32_t kPreyTotal = {len(P["slot"])};
{c_array("double", "kPreyPos", P["pos"], 6, d_lit, comment="[p*2] 이동 뒤 위치")}
{c_array("std::uint8_t", "kPreyBehavior", P["beh"], 40, _i)}
{c_array("std::uint8_t", "kPreyHideArrived", P["arrived"], 40, _i)}
{c_array("std::uint8_t", "kPreyInCover", P["in_cover"], 40, _i)}
{c_array("double", "kPreyRoll", P["roll"], 6, d_lit, comment="[p] 원거리 판정 난수 (원거리형이 아니면 kNoRoll)")}
{c_array("std::int32_t", "kPreySlot", P["slot"], 16, _i, comment="[p] 원래 초식 슬롯 (무대는 0..)")}
	// 기대 (스텝 뒤)
{c_array("double", "kPostPos", A["post_pos"], 6, d_lit, comment="[n*2]")}
{c_array("double", "kPostHead", A["post_head"], 6, d_lit, comment="[n*2]")}
{c_array("double", "kPostVel", A["post_vel"], 6, d_lit, comment="[n*2]")}
{c_array("std::int32_t", "kPostInt", A["post_int"], 15, _i, comment="[n*5] Cooldown, StalkState, StalkLeft, PlayerMode, PlayerLeft")}
{c_array("std::uint8_t", "kOutBits", A["out_bits"], 40, _i, comment="[n] kOut* 비트")}
{c_array("std::int32_t", "kOutTarget", A["target"], 24, _i, comment="[n] 표적 (사례 안 초식 색인, -1 없음)")}
{c_array("double", "kOutTargetPerceived", A["d_t"], 6, d_lit, comment="[n] 표적 체감 거리 (없으면 -1)")}
{c_array("std::int32_t", "kOutCaught", A["caught"], 24, _i, comment="[n] 잡은 초식 (사례 안 색인, -1 없음)")}
{c_array("double", "kOutSpeed", A["speed"], 6, d_lit, comment="[n] 적용 속력")}
}}
"""
    if chr(0xA7) in body:
        raise SystemExit("헤더에 절 기호가 들어갔다")
    Path(path).write_text(body, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------- #


def config_digest(cfg) -> str:
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def rel(path: Path) -> str:
    p = Path(path).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def export(model_path: Path, config: Path, out: Path, seeds=GOLDEN_SEEDS, steps: int = GOLDEN_STEPS) -> dict:
    """헤더를 `out` 에 쓴다. 반환: 메타·골든·통계."""
    import torch as th

    from env_v2.config import load_v2_config
    from export_weights_v3 import load_model

    check_seeds(seeds)
    model_path, config, out = Path(model_path), Path(config), Path(out)
    if not model_path.exists():
        raise SystemExit(f"{model_path} 없음")
    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        model = load_model(model_path)
        cfg = load_v2_config(config)
        g = build_golden(model, cfg, seeds, steps)
    finally:
        th.set_num_threads(prev)
    meta = dict(model=rel(model_path), model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                world_config=rel(config), world_digest=config_digest(cfg))
    out.mkdir(parents=True, exist_ok=True)
    write_header(out / HEADER, g, meta)
    return dict(meta=meta, golden=g, stats=g["stats"])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v3 위협 모델 골든 내보내기")
    p.add_argument("--model", default=str(DEFAULT_MODEL), help="사슴을 모는 R1b 모델")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="학습 세계 (경보 없는 R1 세계)")
    p.add_argument("--seeds", type=int, nargs="+", default=list(GOLDEN_SEEDS))
    p.add_argument("--steps", type=int, default=GOLDEN_STEPS)
    p.add_argument("--out", default=str(UE_POLICY_DIR), help="헤더를 쓸 폴더 (기본: 언리얼 모듈 AI/Policy)")
    args = p.parse_args(argv)
    r = export(Path(args.model), Path(args.config), Path(args.out), args.seeds, args.steps)
    g, s = r["golden"], r["stats"]
    fl = flatten(g)
    kinds = np.bincount(np.array(fl["A"]["kind"]), minlength=len(KIND_NAMES))
    print(f"모델: {r['meta']['model']}  sha256 {r['meta']['model_sha256'][:16]}  세계 {r['meta']['world_config']}")
    print(f"풀: 위협 스텝 {s['pool']} ({', '.join(f'{k} {v}' for k, v in s['pool_by_type'].items())})")
    print(f"사례: {len(fl['cases'])} — " + ", ".join(f"{KIND_NAMES[i]} {kinds[i]}" for i in range(len(KIND_NAMES))))
    print(f"초식: {len(fl['P']['slot'])}개")
    print(f"문턱 근처 제외 {s['near_total']}: " + ", ".join(f"{k} {v}" for k, v in s["near_by_reason"].items()))
    print(f"롤아웃 열: {s['rollout_seqs']}")
    print(f"생성: {Path(args.out) / HEADER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
