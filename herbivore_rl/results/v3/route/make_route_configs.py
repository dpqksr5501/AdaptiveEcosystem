"""두뇌 길(관측 24·마스크 판 4) 설정 두 개 만들기 (10-22 사용자 결정 '두 길 두뇌로 진행' — 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16절).

    # herbivore_rl/ 에서
    python results/v3/route/make_route_configs.py           # configs/v3_wild3_route_mirror.yaml·configs/v3_r6_train.yaml 을 쓴다
    python results/v3/route/make_route_configs.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

configs/v3_wild3_route_mirror.yaml = 머리 주석 + configs/v3_wild3_obs_mirror.yaml 그대로(관측 21 거울 — 언리얼과 같은 세계) + 바꾼 곳 둘
(그 밖의 줄은 한 글자도 바꾸지 않는다):
  1) version "3.wild3obs" → "3.wild3route"
  2) wild_flight.route true: 반사 도주 중 두뇌가 RUN·SHELTER 를 고르고 관측이 24 칸(맨 끝 in_panic·shelter_reach·shelter_edge)이다(마스크 판 4)
  숲 시야(obstacles.foliage)는 끈 채다(게임 기본값 — eco.IntegratedV3.Foliage 0). 판정·두뇌 골든 세계(export_weights_v3.BRAIN_GOLDEN_CONFIG_ROUTE).
configs/v3_r6_train.yaml = 머리 주석 + configs/v3_r5_train.yaml 그대로(R5 학습 조리법 — 무작위 숲 섞기·40 m 밖 부활 포함, 설계 8-2·16-8) + 바꾼 곳 넷:
  1) version "3.r5" → "3.r6"
  2) wild_satiation enabled false: N 세계(늑대 포만 끔 — 설계 0절 '세계 셋'의 N, 16-8 학습 세계)
  3) wild_flight.route true + flight_cost 0.0(자리 — 16-7 후보 {0, 0.0027, 0.005} 는 조기 점검이 고른다)
  4) train.repertoire f_dec·ent_coef_base: 이 세계(마스크 판 4 — 덮기 스텝은 결정이 아니다)에서 다시 잰 값(범주 엔트로피 계수 0.01 그대로)
  train.region_mix(지역 나무 원판 = R5 배치 표, random_forest)는 R5 그대로다. 판정 스냅숏 s20004 의 메마른 땅 시험 나무 20 그루는 지역 표에 없다 —
  무작위 숲 세계(절반)가 나무 배치를 넓게 덮는다(설계 16-8).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
OBS_MIRROR = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"
R5_TRAIN = ROOT / "configs" / "v3_r5_train.yaml"
ROUTE_MIRROR = ROOT / "configs" / "v3_wild3_route_mirror.yaml"
R6_TRAIN = ROOT / "configs" / "v3_r6_train.yaml"

# f_dec: `python train_v3.py measure-fdec --config configs/v3_r6_train.yaml --seeds 32000 32001 32002` (시작 정책 = 모델 시드 0 의 무작위 가중치 + 시작
# 로짓 편향, 지역 셋(언리얼 나무 원판) × 시드 셋 × 3000스텝 — R4·R5 와 같은 정의, 무작위 숲 세계는 재지 않는다. 판 4 라 덮기 스텝을 결정에서 뺀 값,
# SHELTER 는 무효까지 잇는다). 기록 results/v3/route/logs/measure_fdec_r6.log.
# ent_coef_base = 0.01 × f_dec (범주 엔트로피 계수 0.01 — train_v3.py 가 ent_coef_base ÷ f_dec 로 쓴다)
F_DEC = 0.72409             # results/v3/route/logs/measure_fdec_r6.log (10-22, SHELTER 유지·결정 셈 고침 뒤 — 세계 decide_frac 과 같다)
FLIGHT_COST = 0.0

ROUTE_KEY = (
    "    # 10-22 두뇌 길(선택 키 route — 설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16절, env_v2/world.py 모듈 docstring '야생 1단계' (w3) 두뇌 길): 반사 도주 중\n"
    "    # 길 결정 스텝(시작·SHELTER 무효·RUN 길에서 2초 뒤 SHELTER 가능 바뀜)에서 두뇌가 칸 1 RUN(지금 반사 방향)·칸 4 SHELTER(늑대보다 먼저 닿는 은신처)를\n"
    "    # 고른다. SHELTER 는 무효(늑대가 문에 먼저 닿음)까지 잇는다.\n"
    "    # 관측 24(맨 끝 in_panic·shelter_reach·shelter_edge), 마스크 판 4(칸 3 은 늘 막힘). 실행 행동은 늘 FLEE\n"
    "    route: true\n")

MIRROR_HEAD = """\
# 두뇌 길 거울 세계 — 관측 21 거울(언리얼 통합 레벨과 같은 세계)에 두뇌가 반사 도주 중 RUN·SHELTER 를 고르는 길을 켠다 (10-22 사용자 결정 '두 길 두뇌로 진행',
# 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16절).
# 자동 생성 — results/v3/route/make_route_configs.py (손으로 고치지 않는다. v3_wild3_obs_mirror.yaml 이 바뀌면 다시 만든다).
# = configs/v3_wild3_obs_mirror.yaml(아래 그대로) + 바꾼 곳 둘: version 3.wild3route, wild_flight.route true. 관측 21 → 24 칸(앞 21 칸은 비트 단위로 같다),
#   마스크 판 4(계약 해시 0xe302dee198197444 — export_weights_v3.contract_hash). 숲 시야는 끈 채다(게임 기본값).
# 재기 전용 세계(부활 없음) — R6 판정·두뇌 골든 세계. 판 4 두뇌만 돈다(관측 21 두뇌는 v3_wild3_obs_mirror.yaml — 길 끈 세계와 '켬 + 늘 RUN' 은 궤적이 같다,
# tests/test_route2_v3.py). 시드: 탐색 32000~32099, R6 판정 37000~37099(설계 16-9 — 학습 전 PREREG 에 적는다).
#
# ── 아래는 v3_wild3_obs_mirror.yaml 그대로 (version 과 wild_flight.route 만 다르다) ──
"""

R6_HEAD = """\
# v3 R6 학습 세계 — 두뇌 길(관측 24·마스크 판 4)로 시작 두뇌 route0(= R1b-F + 0열, 길 칸 4 = 칸 1 − 2)을 이어 배운다 (10-22 사용자 결정 '두 길 두뇌로
# 진행', 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16-6~16-8).
# 자동 생성 — results/v3/route/make_route_configs.py (손으로 고치지 않는다. v3_r5_train.yaml 이 바뀌면 다시 만든다).
# = configs/v3_r5_train.yaml(R5 학습 조리법 — 무작위 숲 섞기·40 m 밖 부활 포함, 아래 그대로) + 바꾼 곳 넷 (학습 세계 = N + R5 조리법 + 무리 사냥 + 길,
#   설계 8-2·16-8):
#   1) version 3.r6
#   2) wild_satiation enabled false: N 세계(늑대 포만 끔 — 판정 1차 P1 세계와 같다)
#   3) wild_flight.route true(두뇌 길) + flight_cost 0.0(자리 — 후보 {0, 0.0027, 0.005} 는 조기 점검이 고른다, 16-7)
#   4) train.repertoire f_dec·ent_coef_base: 이 세계에서 다시 잰 시작 정책 결정 비율(판 4 — 덮기 스텝은 결정이 아니다. 범주 엔트로피 계수 0.01 그대로)
# 지역 나무 원판은 R5 배치 표(메마른 땅 0 그루)다. 판정 스냅숏 s20004 의 메마른 땅 시험 나무 20 그루는 없다 — 무작위 숲 세계(절반)가 덮는다(16-8).
# 시작: python train_v3.py --config configs/v3_r6_train.yaml --init-from-model ckpt/v3/v3_r1_g995_s3_obs24route0.zip --init-source "…" (route_extend.py).
# 판정은 부활 없는 거울 세계(configs/v3_wild3_route_mirror.yaml, N 은 wild_satiation 끔)에서 파이썬으로 한다(길은 아직 C++ 평가기에 없다).
# 시드: 학습 32000~32049(R5 와 같다), 스모크 32080~32099, 모델 고르기 37100~37119, 조기 점검 37120~37139, 판정 37000~37099.
#
# ── 아래는 v3_r5_train.yaml 그대로 (위 넷만 다르다) ──
"""


def _sub(src: str, old: str, new: str, what: str) -> str:
    if src.count(old) != 1:
        raise SystemExit(f"{what} 에서 바꿀 줄을 하나로 못 찾았다: {old[:80]!r} — 생성기를 고친다")
    return src.replace(old, new, 1)


def render_mirror() -> str:
    src = OBS_MIRROR.read_text(encoding="utf-8")
    src = _sub(src, 'version: "3.wild3obs"', 'version: "3.wild3route"', OBS_MIRROR.name)
    src = _sub(src, "    hold_awake: true\n    edge_r: 5.0\n", "    hold_awake: true\n    edge_r: 5.0\n" + ROUTE_KEY, OBS_MIRROR.name)
    return MIRROR_HEAD + src


def render_r6(f_dec: float = F_DEC) -> str:
    if not 0.0 < f_dec <= 1.0:
        raise SystemExit(f"F_DEC {f_dec} 가 (0, 1] 가 아니다 — measure-fdec 로 잰 값을 적는다")
    src = R5_TRAIN.read_text(encoding="utf-8")
    w = R5_TRAIN.name
    src = _sub(src, 'version: "3.r5"', 'version: "3.r6"', w)
    src = _sub(src, "  wild_satiation:\n    enabled: true\n",
               "  wild_satiation:\n"
               "    # R6: N 세계(늑대 포만 끔 — 설계 0절 '세계 셋'의 N, 판정 1차 P1 세계와 같다)\n"
               "    enabled: false\n", w)
    src = _sub(src, "    hold_awake: true\n    edge_r: 5.0\n",
               "    hold_awake: true\n    edge_r: 5.0\n"
               "    # R6 학습 세계 전용 도주 비용(자리 0 — 후보 {0, 0.0027, 0.005} 는 조기 점검이 고른다, 설계 16-7)\n"
               f"    flight_cost: {FLIGHT_COST!r}\n" + ROUTE_KEY, w)
    if src.count("    random_forest:\n") != 1:     # R5 무작위 숲 섞기는 그대로 둔다(설계 8-2 '무작위 숲 14~21' — 16-8 학습 세계)
        raise SystemExit(f"{w} 에 train.region_mix.random_forest 가 하나가 아니다 — R6 학습 세계는 R5 조리법 그대로다")
    src = _sub(src, "    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = 이 세계(지역 셋, 언리얼 나무 원판)에서 잰 시작 정책 결정 비율(results/v3/r5/logs/measure_fdec.log)\n"
                    "    ent_coef_base: 0.00858922\n    f_dec: 0.858922\n",
               "    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = R6 세계(지역 셋, 언리얼 나무 원판, 마스크 판 4)에서 잰 시작 정책 결정 비율\n"
               "    # (results/v3/route/logs/measure_fdec_r6.log — 덮기 스텝은 결정이 아니라 R5 의 0.858922 보다 작다)\n"
               f"    ent_coef_base: {round(0.01 * f_dec, 8)!r}\n    f_dec: {f_dec!r}\n", w)
    return R6_HEAD + src


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--f-dec", type=float, default=None, help="F_DEC 대신 이 값 (measure-fdec 를 돌리기 전 임시 설정용)")
    a = ap.parse_args(argv)
    out = {ROUTE_MIRROR: render_mirror(), R6_TRAIN: render_r6(F_DEC if a.f_dec is None else a.f_dec)}
    if a.check:
        bad = [p.name for p, t in out.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        print("최신이다" if not bad else f"{bad} 가 지금 규칙으로 만든 것과 다르다 — 다시 만든다")
        return 1 if bad else 0
    for p, t in out.items():
        p.write_text(t, encoding="utf-8", newline="\n")
        print(f"-> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
