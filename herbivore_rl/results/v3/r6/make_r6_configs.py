"""v3 R6 학습 설정의 갈래 만들기 (사전 등록 results/v3/r6/PREREG.md 1·3절 — 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16-7·16-8).

    # herbivore_rl/ 에서
    python results/v3/r6/make_r6_configs.py           # 아래 여섯 파일을 쓴다
    python results/v3/r6/make_r6_configs.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

바탕 = configs/v3_r6_train.yaml (c109bf0 — results/v3/route/make_route_configs.py 가 만든 R6 학습 세계: R5 학습 조리법 + 늑대 포만 끔 + 두뇌 길 +
무작위 숲 섞기 그대로, f_dec 0.724090). 바탕은 고치지 않는다(도주 비용 0 판 = 바탕 그대로).
  - configs/v3_r6_train_c0027.yaml · configs/v3_r6_train_c005.yaml: 바탕에서 wild_flight.flight_cost 줄만 0.0027 · 0.005 로 (설계 16-7 후보).
    도주 비용은 보상에만 들어간다(env_v2/world.py `step` 5) — 동역학·관측·난수·f_dec 는 그대로다).
  - configs/v3_r6off_train.yaml · _c0027 · _c005: 대조 '길 끔'(설계 16-8 2) = 바탕에서 version 3.r6off, wild_flight.route false(관측 21·마스크 판 2),
    f_dec·ent_coef_base 를 이 세계에서 잰 값으로, 도주 비용은 위와 같다. 범주 엔트로피 계수 0.01 은 그대로다(ent_coef_base = 0.01 × f_dec).
  - configs/ppo_r6_lam098.yaml: configs/ppo_best.yaml 의 params 그대로 + gae_lambda 0.98 (설계 16-8 1 의 λ 후보. λ 0.95 는 ppo_best.yaml 그대로 —
    train.PPO_KWARGS 의 gae_lambda 0.95. train_v3.make_model_rep 이 PPO 설정 params 로 PPO_KWARGS 를 덮는다).
그 밖의 줄은 한 글자도 바꾸지 않는다(시험 tests/test_r6_prereg.py 가 YAML 로 읽어 바꾼 칸만 다른지 본다).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
CONFIGS = ROOT / "configs"
BASE = CONFIGS / "v3_r6_train.yaml"
PPO_BEST = CONFIGS / "ppo_best.yaml"
PPO_LAM98 = CONFIGS / "ppo_r6_lam098.yaml"

COSTS = {"0": 0.0, "0027": 0.0027, "005": 0.005}          # 이름 조각 → 도주 비용 c (설계 16-7 후보)
LAMBDAS = {"95": 0.95, "98": 0.98}                         # 이름 조각 → GAE λ (설계 16-8 1)
# 길 끔 대조 세계의 시작 정책 결정 비율 — `python train_v3.py measure-fdec --config configs/v3_r6off_train.yaml --seeds 32000 32001 32002`
# (지역 셋(언리얼 나무 원판) × 시드 셋 × 3000스텝, 시작 정책 = 모델 시드 0 의 무작위 가중치 + 시작 로짓 편향 — R4·R5·R6 와 같은 정의).
# 기록 results/v3/r6/logs/measure_fdec_off.log
F_DEC_OFF = 0.873641

COST_LINE = "    flight_cost: 0.0\n"
ROUTE_LINE = "    route: true\n"
FDEC_OLD = ("    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = R6 세계(지역 셋, 언리얼 나무 원판, 마스크 판 4)에서 잰 시작 정책 결정 비율\n"
            "    # (results/v3/route/logs/measure_fdec_r6.log — 덮기 스텝은 결정이 아니라 R5 의 0.858922 보다 작다)\n"
            "    ent_coef_base: 0.0072409\n    f_dec: 0.72409\n")


def config_path(route: bool, cost: str) -> Path:
    """학습 설정 파일: 길 켬·도주 비용 0 = 바탕(configs/v3_r6_train.yaml), 그 밖은 갈래."""
    if cost not in COSTS:
        raise ValueError(f"도주 비용 이름 {cost!r} 는 {sorted(COSTS)} 가운데 하나다")
    stem = "v3_r6_train" if route else "v3_r6off_train"
    return CONFIGS / (f"{stem}.yaml" if cost == "0" else f"{stem}_c{cost}.yaml")


def ppo_path(lam: str) -> Path:
    """PPO 설정 파일: λ 0.95 = configs/ppo_best.yaml 그대로, λ 0.98 = configs/ppo_r6_lam098.yaml."""
    if lam not in LAMBDAS:
        raise ValueError(f"λ 이름 {lam!r} 는 {sorted(LAMBDAS)} 가운데 하나다")
    return PPO_BEST if lam == "95" else PPO_LAM98


def _sub(src: str, old: str, new: str, what: str) -> str:
    if src.count(old) != 1:
        raise SystemExit(f"{what} 에서 바꿀 줄을 하나로 못 찾았다: {old[:80]!r} — 생성기를 고친다")
    return src.replace(old, new, 1)


def _head(route: bool, cost: str) -> str:
    c = COSTS[cost]
    if route:
        what = (f"# v3 R6 학습 세계 갈래 — 도주 비용 c = {c!r} (설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16-7 후보, 사전 등록 results/v3/r6/PREREG.md 1-2).\n"
                "# 자동 생성 — results/v3/r6/make_r6_configs.py (손으로 고치지 않는다. configs/v3_r6_train.yaml 이 바뀌면 다시 만든다).\n"
                f"# = configs/v3_r6_train.yaml(아래 그대로) + 바꾼 곳 하나: wild_flight.flight_cost {c!r} (FLEE 를 실행한 사슴-스텝마다 보상에서 뺀다 — 보상 전용).\n")
    else:
        what = (f"# v3 R6 대조 '길 끔' 학습 세계 — 관측 21·마스크 판 2, 도주 비용 c = {c!r} (설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16-8 2, 사전 등록\n"
                "# results/v3/r6/PREREG.md 1-3). 시작 두뇌 obs21zero(ckpt/v3/v3_r1_g995_s3_obs21zero.zip). R6 와 같은 T 세계·λ·c 에서 길만 끈다.\n"
                "# 자동 생성 — results/v3/r6/make_r6_configs.py (손으로 고치지 않는다. configs/v3_r6_train.yaml 이 바뀌면 다시 만든다).\n"
                "# = configs/v3_r6_train.yaml(아래 그대로) + 바꾼 곳: version 3.r6off, wild_flight.route false"
                + (f", wild_flight.flight_cost {c!r}" if c > 0 else "") + ",\n"
                f"#   train.repertoire f_dec {F_DEC_OFF!r}·ent_coef_base(이 세계에서 잰 값 — results/v3/r6/logs/measure_fdec_off.log, 범주 엔트로피 계수 0.01 그대로).\n")
    return what + "#\n# ── 아래는 configs/v3_r6_train.yaml 그대로 (위에 적은 곳만 다르다) ──\n"


def render(route: bool, cost: str, f_dec_off: float = F_DEC_OFF) -> str:
    src = BASE.read_text(encoding="utf-8")
    w = BASE.name
    c = COSTS[cost]
    if c > 0:
        src = _sub(src, COST_LINE, f"    flight_cost: {c!r}\n", w)
    else:
        _sub(src, COST_LINE, COST_LINE, w)               # 바탕에 자리 줄이 있는지만 본다
    if not route:
        if not 0.0 < f_dec_off <= 1.0:
            raise SystemExit(f"F_DEC_OFF {f_dec_off} 가 (0, 1] 가 아니다 — measure-fdec 로 잰 값을 적는다")
        src = _sub(src, 'version: "3.r6"', 'version: "3.r6off"', w)
        src = _sub(src, ROUTE_LINE, "    # R6 대조 '길 끔'(설계 16-8 2): 두뇌 길을 끈다 — 관측 21·마스크 판 2(R5 와 같은 계약)\n    route: false\n", w)
        src = _sub(src, FDEC_OLD,
                   "    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = R6 대조 '길 끔' 세계(지역 셋, 언리얼 나무 원판, 마스크 판 2)에서 잰 시작 정책 결정 비율\n"
                   "    # (results/v3/r6/logs/measure_fdec_off.log)\n"
                   f"    ent_coef_base: {round(0.01 * f_dec_off, 8)!r}\n    f_dec: {f_dec_off!r}\n", w)
    return _head(route, cost) + src


def render_ppo() -> str:
    src = PPO_BEST.read_text(encoding="utf-8")
    head = ("# R6 λ 후보 0.98 (설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16-8 1, 사전 등록 results/v3/r6/PREREG.md 3절). 자동 생성 — results/v3/r6/make_r6_configs.py.\n"
            "# = configs/ppo_best.yaml(아래 그대로) + params.gae_lambda 0.98. train_v3.make_model_rep 이 params 로 train.PPO_KWARGS(gae_lambda 0.95)를 덮는다.\n"
            "# γ 는 train_v3.py 가 0.995(S1-a)로 정한다(params.gamma 는 쓰이지 않는다 — ppo_best.yaml 과 같다).\n")
    return head + _sub(src, "  n_epochs: 15\n", "  n_epochs: 15\n  gae_lambda: 0.98\n", PPO_BEST.name)


def outputs(f_dec_off: float = F_DEC_OFF) -> dict:
    out = {config_path(r, c): render(r, c, f_dec_off) for r in (True, False) for c in COSTS if not (r and c == "0")}
    out[PPO_LAM98] = render_ppo()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--f-dec-off", type=float, default=None, help="F_DEC_OFF 대신 이 값 (measure-fdec 를 돌리기 전 임시 설정용)")
    a = ap.parse_args(argv)
    out = outputs(F_DEC_OFF if a.f_dec_off is None else a.f_dec_off)
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
