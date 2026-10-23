"""R7 설정 셋 만들기 — 반사 밖 두뇌 FLEE 막음(마스크 판 5·6) (10-23 사람 결정 '짧게 진단 후 R7' — 설계
AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 17절, 판정 뒤 진단 results/v3/r6/diag/diag.md 'GO').

    # herbivore_rl/ 에서
    python results/v3/r7/make_r7_configs.py           # 아래 세 파일을 쓴다
    python results/v3/r7/make_r7_configs.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

세 파일 (그 밖의 줄은 한 글자도 바꾸지 않는다 — 시험 tests/test_r7_mask5.py 가 YAML 로 읽어 바꾼 칸만 다른지 본다):
  configs/v3_wild3_route5_mirror.yaml = 머리 주석 + configs/v3_wild3_route_mirror.yaml 그대로(R6 판정·두뇌 골든 거울, 관측 24) + 바꾼 곳 둘:
    1) version "3.wild3route" → "3.wild3route5"
    2) wild_flight.brain_flee_outside_reflex false (마스크 판 5 = 판 4 + 반사 밖 두뇌 FLEE 막음)
    R7 판정 거울·판 5 두뇌 골든 세계(export_weights_v3.BRAIN_GOLDEN_CONFIG_ROUTE5).
  configs/v3_r7_train.yaml = 머리 주석 + configs/v3_r6_train.yaml 그대로(R6 학습 세계 — R5 조리법·늑대 포만 끔·두뇌 길·도주 비용 0) + 바꾼 곳 셋:
    1) version "3.r6" → "3.r7"
    2) wild_flight.brain_flee_outside_reflex false (마스크 판 5)
    3) train.repertoire f_dec·ent_coef_base: 이 세계에서 다시 잰 시작 정책 결정 비율(범주 엔트로피 계수 0.01 그대로)
    λ 0.98 · 도주 비용 0 은 R6 조기 점검이 고른 값(results/v3/r6/logs/early_pick.json)으로 고정한다: 도주 비용은 바탕의 flight_cost 0.0 그대로,
    λ 는 PPO 설정 configs/ppo_r6_lam098.yaml(PPO_CONFIG — gae_lambda 0.98)을 쓴다(train_v3.py --ppo-config).
  configs/v3_r7off_train.yaml = 대조 '길 끔' — 위 v3_r7_train.yaml 그대로 + 바꾼 곳 셋: version 3.r7off, wild_flight.route false(관측 21),
    train.repertoire f_dec·ent_coef_base(이 세계에서 잰 값). 반사 밖 FLEE 막기는 그대로라 마스크 판 6(= 판 2 + 막기 + 덮기 줄 한 칸)이다.
    시작 두뇌는 obs21zero 의 판만 6 으로 붙인 ckpt/v3/v3_r1_g995_s3_obs21zero_m6.zip (results/v3/r7/r7_start.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
CONFIGS = ROOT / "configs"
ROUTE_MIRROR = CONFIGS / "v3_wild3_route_mirror.yaml"
R6_TRAIN = CONFIGS / "v3_r6_train.yaml"
ROUTE5_MIRROR = CONFIGS / "v3_wild3_route5_mirror.yaml"
R7_TRAIN = CONFIGS / "v3_r7_train.yaml"
R7OFF_TRAIN = CONFIGS / "v3_r7off_train.yaml"
PPO_CONFIG = CONFIGS / "ppo_r6_lam098.yaml"        # λ 0.98 (R6 조기 점검이 고른 값 — results/v3/r6/logs/early_pick.json)

# f_dec: `python train_v3.py measure-fdec --config configs/v3_r7_train.yaml --seeds 32000 32001 32002` (시작 정책 = 모델 시드 0 의 무작위 가중치 + 시작
# 로짓 편향, 지역 셋(언리얼 나무 원판) × 시드 셋 × 3000스텝 — R4·R5·R6 와 같은 정의, 무작위 숲 세계는 재지 않는다. 판 5 라 덮기 밖 결정에서 FLEE 가 막혀
# 궤적이 R6 와 다르다). 기록 results/v3/r7/logs/measure_fdec_r7.log. 대조는 --config configs/v3_r7off_train.yaml → logs/measure_fdec_r7off.log.
# ent_coef_base = 0.01 × f_dec (범주 엔트로피 계수 0.01 — train_v3.py 가 ent_coef_base ÷ f_dec 로 쓴다)
# (10-23 잼: R6 의 0.724090 보다 조금 작다. 대조는 R6 대조 0.873641 보다 크게 작다 — 판 6 은 판 2 와 달리 덮기 스텝을 결정에서 뺀다)
F_DEC = 0.714694            # results/v3/r7/logs/measure_fdec_r7.log (덮기 밖 두뇌 FLEE 0 — gate_flee)
F_DEC_OFF = 0.708908        # results/v3/r7/logs/measure_fdec_r7off.log

ROUTE_LINE = "    route: true\n"
GATE_KEY = (
    "    # 10-23 R7 반사 밖 두뇌 FLEE 막음(선택 키 brain_flee_outside_reflex — 설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 17절, env_v2/world.py 모듈 docstring\n"
    "    # '반사 밖 두뇌 FLEE 막음'): 도주 반사(덮기) 밖 결정에서 두뇌가 칸 1(FLEE)을 고르지 못한다 — 도주는 반사만 시작하고 두뇌는 '어디로'(RUN·SHELTER)만\n"
    "    # 고른다. 막기는 마스크가 한다(동역학·관측·보상 그대로). 두뇌 길을 켠 세계는 마스크 판 5, 끈 세계는 판 6\n"
    "    brain_flee_outside_reflex: false\n")
FDEC_R6 = ("    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = R6 세계(지역 셋, 언리얼 나무 원판, 마스크 판 4)에서 잰 시작 정책 결정 비율\n"
           "    # (results/v3/route/logs/measure_fdec_r6.log — 덮기 스텝은 결정이 아니라 R5 의 0.858922 보다 작다)\n"
           "    ent_coef_base: 0.0072409\n    f_dec: 0.72409\n")

MIRROR_HEAD = """\
# 반사 밖 두뇌 FLEE 막음 거울 세계 — 두뇌 길 거울(관측 24)에 마스크 판 5(= 판 4 + 덮기 밖 결정에서 칸 1 FLEE 막음)를 켠다 (10-23 사람 결정 '짧게 진단 후 R7',
# 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 17절).
# 자동 생성 — results/v3/r7/make_r7_configs.py (손으로 고치지 않는다. v3_wild3_route_mirror.yaml 이 바뀌면 다시 만든다).
# = configs/v3_wild3_route_mirror.yaml(아래 그대로) + 바꾼 곳 둘: version 3.wild3route5, wild_flight.brain_flee_outside_reflex false.
#   관측 24 는 그대로, 계약은 관측 24·판 5(export_weights_v3.contract_hash — flight_route 와 brain_flee_outside_reflex false 키). 세계 동역학은 판 4 거울과
#   같다(같은 행동이면 궤적이 비트 단위로 같다 — 막기는 마스크만).
# 재기 전용 세계(부활 없음) — R7 판정·판 5 두뇌 골든 세계. 판 5 두뇌만 돈다(판 4 두뇌·route0 은 v3_wild3_route_mirror.yaml, 판 5 시작 두뇌 route0m5 는
# 가중치가 route0 과 같다 — results/v3/r7/r7_start.py).
#
# ── 아래는 v3_wild3_route_mirror.yaml 그대로 (version 과 wild_flight.brain_flee_outside_reflex 만 다르다) ──
"""

R7_HEAD = """\
# v3 R7 학습 세계 — 반사 밖 두뇌 FLEE 막음(마스크 판 5 = 판 4 + 덮기 밖 결정에서 칸 1 FLEE 막음)으로 시작 두뇌 route0m5(= route0 가중치 그대로, 판만 5)를
# 이어 배운다 (10-23 사람 결정 '짧게 진단 후 R7' — 판정 뒤 진단 results/v3/r6/diag/diag.md 'GO', 설계 AdaptiveEcosystem/Docs/RL_Policy/
# RL_V3_FLIGHT_ROUTE_DESIGN.md 17절).
# 자동 생성 — results/v3/r7/make_r7_configs.py (손으로 고치지 않는다. v3_r6_train.yaml 이 바뀌면 다시 만든다).
# = configs/v3_r6_train.yaml(R6 학습 세계 — R5 조리법·늑대 포만 끔·두뇌 길, 아래 그대로) + 바꾼 곳 셋:
#   1) version 3.r7
#   2) wild_flight.brain_flee_outside_reflex false (마스크 판 5 — 반사가 '언제', 두뇌가 '어디로')
#   3) train.repertoire f_dec·ent_coef_base: 이 세계에서 다시 잰 시작 정책 결정 비율(범주 엔트로피 계수 0.01 그대로)
# λ 0.98 · 도주 비용 0 은 R6 조기 점검이 고른 값으로 고정한다(results/v3/r6/logs/early_pick.json): 도주 비용은 아래 flight_cost 0.0 그대로,
# λ 는 PPO 설정 configs/ppo_r6_lam098.yaml 을 쓴다.
# 시작: python train_v3.py --config configs/v3_r7_train.yaml --ppo-config configs/ppo_r6_lam098.yaml --init-from-model ckpt/v3/v3_r1_g995_s3_obs24route0m5.zip
#   --init-source "…" (results/v3/r7/r7_start.py). 판정 거울은 configs/v3_wild3_route5_mirror.yaml(파이썬 — 판 5 는 아직 C++ 평가기에 없다).
# 시드는 R7 사전 등록(학습 전)이 정한다 — R6 판정 37000~37099·고르기 37100~37119·조기 점검 37120~37139 는 R7 판정·고르기에 다시 쓰지 않는다.
#
# ── 아래는 v3_r6_train.yaml 그대로 (위 셋만 다르다) ──
"""


def _sub(src: str, old: str, new: str, what: str) -> str:
    if src.count(old) != 1:
        raise SystemExit(f"{what} 에서 바꿀 줄을 하나로 못 찾았다: {old[:80]!r} — 생성기를 고친다")
    return src.replace(old, new, 1)


def _fdec_block(f_dec: float, where: str, log: str) -> str:
    if not 0.0 < f_dec <= 1.0:
        raise SystemExit(f"f_dec {f_dec} 가 (0, 1] 가 아니다 — measure-fdec 로 잰 값을 F_DEC·F_DEC_OFF 에 적는다(재기 전에는 --f-dec·--f-dec-off 로 자리 값)")
    return (f"    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = {where}에서 잰 시작 정책 결정 비율\n"
            f"    # ({log})\n"
            f"    ent_coef_base: {round(0.01 * f_dec, 8)!r}\n    f_dec: {f_dec!r}\n")


def render_mirror() -> str:
    src = ROUTE_MIRROR.read_text(encoding="utf-8")
    w = ROUTE_MIRROR.name
    src = _sub(src, 'version: "3.wild3route"', 'version: "3.wild3route5"', w)
    src = _sub(src, ROUTE_LINE, ROUTE_LINE + GATE_KEY, w)
    return MIRROR_HEAD + src


def render_r7(f_dec: float = F_DEC) -> str:
    src = R6_TRAIN.read_text(encoding="utf-8")
    w = R6_TRAIN.name
    src = _sub(src, 'version: "3.r6"', 'version: "3.r7"', w)
    _sub(src, "    flight_cost: 0.0\n", "    flight_cost: 0.0\n", w)           # 도주 비용 0(R6 조기 점검이 고른 값) — 바탕에 그 줄이 있는지만 본다
    src = _sub(src, ROUTE_LINE, ROUTE_LINE + GATE_KEY, w)
    src = _sub(src, FDEC_R6, _fdec_block(f_dec, "R7 세계(지역 셋, 언리얼 나무 원판, 마스크 판 5)", "results/v3/r7/logs/measure_fdec_r7.log"), w)
    return R7_HEAD + src


def render_r7off(f_dec: float = F_DEC, f_dec_off: float = F_DEC_OFF) -> str:
    src = render_r7(f_dec)
    w = R7_TRAIN.name
    src = _sub(src, 'version: "3.r7"', 'version: "3.r7off"', w)
    src = _sub(src, ROUTE_LINE, "    # R7 대조 '길 끔'(설계 17절): 두뇌 길을 끈다 — 관측 21, 반사 밖 FLEE 막기는 그대로라 마스크 판 6\n    route: false\n", w)
    src = _sub(src, _fdec_block(f_dec, "R7 세계(지역 셋, 언리얼 나무 원판, 마스크 판 5)", "results/v3/r7/logs/measure_fdec_r7.log"),
               _fdec_block(f_dec_off, "R7 대조 '길 끔' 세계(지역 셋, 언리얼 나무 원판, 마스크 판 6)", "results/v3/r7/logs/measure_fdec_r7off.log"), w)
    head = ("# v3 R7 대조 '길 끔' 학습 세계 — 관측 21·마스크 판 6(= 판 2 + 반사 밖 두뇌 FLEE 막음 + 덮기 줄 한 칸 — 파이썬 학습 대조 전용) (10-23, 설계\n"
            "# RL_V3_FLIGHT_ROUTE_DESIGN.md 17절). R7 과 같은 T 세계·λ·c·FLEE 막기에서 두뇌 길만 끈다. 시작 두뇌 obs21zero 의 판만 6 으로 붙인\n"
            "# ckpt/v3/v3_r1_g995_s3_obs21zero_m6.zip (results/v3/r7/r7_start.py).\n"
            "# 자동 생성 — results/v3/r7/make_r7_configs.py (손으로 고치지 않는다. configs/v3_r7_train.yaml 이 바뀌면 다시 만든다).\n"
            "# = configs/v3_r7_train.yaml(아래 그대로) + 바꾼 곳: version 3.r7off, wild_flight.route false,\n"
            f"#   train.repertoire f_dec {f_dec_off!r}·ent_coef_base(이 세계에서 잰 값 — results/v3/r7/logs/measure_fdec_r7off.log, 범주 엔트로피 계수 0.01 그대로).\n"
            "#\n# ── 아래는 configs/v3_r7_train.yaml 그대로 (위에 적은 곳만 다르다) ──\n")
    return head + src


def outputs(f_dec: float = F_DEC, f_dec_off: float = F_DEC_OFF) -> dict:
    if PPO_CONFIG.read_text(encoding="utf-8").count("\n  gae_lambda: 0.98\n") != 1:
        raise SystemExit(f"{PPO_CONFIG.name} 에 params.gae_lambda 0.98 이 없다 — R7 은 R6 조기 점검이 고른 λ 0.98 을 쓴다")
    return {ROUTE5_MIRROR: render_mirror(), R7_TRAIN: render_r7(f_dec), R7OFF_TRAIN: render_r7off(f_dec, f_dec_off)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--f-dec", type=float, default=None, help="F_DEC 대신 이 값 (measure-fdec 를 돌리기 전 임시 설정용)")
    ap.add_argument("--f-dec-off", type=float, default=None, help="F_DEC_OFF 대신 이 값 (measure-fdec 를 돌리기 전 임시 설정용)")
    a = ap.parse_args(argv)
    out = outputs(F_DEC if a.f_dec is None else a.f_dec, F_DEC_OFF if a.f_dec_off is None else a.f_dec_off)
    if a.check:
        bad = [p.name for p, t in out.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        print("최신이다" if not bad else f"{bad} 가 지금 규칙으로 만든 것과 다르다 — 다시 만든다")
        return 1 if bad else 0
    for p, t in out.items():
        p.write_text(t, encoding="utf-8", newline="\n")
        print(f"-> {p.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
