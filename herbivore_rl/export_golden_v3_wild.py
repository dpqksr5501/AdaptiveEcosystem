"""v3 야생 1단계 골든 내보내기 — 파이썬 야생 규칙(env_v2/world.py '야생 1단계')을 언리얼 C++ `EcoWorldV3.h` 와 대조할 골든 헤더를 만든다
(명세 `Docs/RL_Policy/RL_V3_WILD1_SPEC.md` 5절 '골든 시험').

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_wild.py
    # 시험용 다른 폴더
    python export_golden_v3_wild.py --out <폴더>

세계·시드:
  - 세계: configs/v3_wild1_mirror.yaml (사람 결정 10-15 (7) 야생 1단계 거울 세계). 계수는 그 세계가 읽은 값(`World._wr`)을 그대로 싣는다.
  - 시드: 탐색 시드 32090 하나(세계를 만들기만 하고 난수 궤적은 쓰지 않는다). 판정 시드는 쓰지 않는다.
  - C++ 와 파이썬은 난수열이 달라 궤적 대조는 하지 않는다(명세 5절). 대신 난수 없는 장면을 파이썬 함수 그대로 돌려 적는다.

묶음 (지금은 (w1) 지방 비축만 — 뒤 규칙은 같은 헤더에 묶음을 더한다):
  비축 한 번  `World._wild_reserve_step` 을 한 번 부른 사례. 입력 (e_new, 먹은 에너지, R) → 출력 (E, R). 모자람을 다 채움·못 채움·R 0,
              채움·빈자리로 자름·R 가득·문턱 아래·먹지 않음·문턱 정확히 같음 같은 끝 사례.
  굶음 열     걷기 대사만(스텝마다 e_new = E − energy_drain, 먹이 0)으로 E 0.5·R 가득에서 굶어 죽을 때까지. 죽는 스텝(명세: 2950)과
              100 스텝마다의 (E, R).
  섞음 열     정해진 먹이 무늬(스텝 t 의 먹은 에너지 = 0.03 if (t // 50) % 3 == 0 else 0, e_new = min(E − drain + 먹은 것, max_energy))로
              E 0.2·R 0.2 에서 600 스텝. 스텝마다 (E, R). C++ 은 같은 식으로 자기 출력을 이어 쓴다.
  포만 열     (w2) 늑대 포만. 거울 세계를 만든 뒤 사슴을 모두 (1, 1) 로, 늑대 둘(추격형·잠행형)을 무대 가운데 (30, 30) 로 옮기고, 낮(d = 0)·
              깨어 있음·밤잠 활동도 가득·속력 배수 1 로 두고, 막 잡은 늑대처럼 쿨다운 = pred_eat_cd(38)·배부름 = sat 스텝(450)에서
              `World._step_predators_v3` 만 500 번 부른다(사슴은 시야 밖이라 표적·포획이 없다). 스텝마다 늑대별 (쿨다운, 남은 배부름,
              배부름 훅, 지난 변위 크기). 변위 크기는 벽에 닿은 스텝만 속력보다 작다.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from env_v2.config import load_v2_config
from env_v2.world import World

HERE = Path(__file__).resolve().parent
WILD = HERE / "configs" / "v3_wild1_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED = 32090
N = 16


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"헤더에 유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s or "inf" in s) else s + ".0"


def c_array(ctype: str, name: str, flat: list, per_line: int, fmt) -> str:
    if not flat:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    lines = [f"\tinline constexpr {ctype} {name}[{len(flat)}] = {{"]
    for k in range(0, len(flat), per_line):
        lines.append("\t\t" + ", ".join(fmt(v) for v in flat[k:k + per_line]) + ",")
    lines.append("\t};")
    return "\n".join(lines)


def make_world() -> World:
    w = World(load_v2_config(WILD).replace(N=N), seeds=[SEED])
    w.reset()
    if w._wr is None:
        raise SystemExit("v3_wild1_mirror.yaml 의 wild_reserve 가 꺼졌다")
    return w


def reserve_once(w: World, e_new: float, gain_e: float, r: float) -> tuple[float, float]:
    """`World._wild_reserve_step` 을 한 번(모든 행 같은 값) 부르고 0 행의 (E, R) 를 돌려준다."""
    w.reserve = np.full(w.N, float(r))
    e = w._wild_reserve_step(np.full(w.N, float(e_new)), np.full(w.N, float(gain_e)), None)
    return float(e[0]), float(w.reserve[0])


def reserve_cases(w: World) -> list[tuple[float, float, float, float, float]]:
    re = w._wr["refill_e"]
    ins = [
        (-0.002, 0.0, 1.0),            # 걷기 대사 한 스텝 — 다 채움
        (-0.002, 0.0, 0.0),            # R 0 — 못 채움, E 그대로
        (-0.01, 0.0, 0.001),           # R 이 모자람보다 작다 — R 0, E = 남은 모자람
        (-0.0054, 0.0, 0.001),         # 모자람 = R·C 정확히 (부동소수 경계 — 덮음 판정 want <= r0)
        (0.0, 0.0, 0.5),               # E 0 정확히 — 꺼내지 않음
        (0.8, 0.03, 0.5),              # 채움 (문턱 위, 먹음)
        (0.8, 0.03, 0.999),            # 빈자리 (1 − R)·C 로 자름
        (0.8, 0.03, 1.0),              # R 가득 — 채우지 않음
        (0.69, 0.03, 0.5),             # 문턱 아래 — 채우지 않음
        (0.8, 0.0, 0.5),               # 먹지 않음 — 채우지 않음
        (re, 0.02, 0.3),               # 문턱 정확히 — 채움 (e_out >= refill_e)
        (1.0, 0.06, 0.0),              # 배 가득·R 빈 — 한 스텝 최대 채움
        (-0.002, 0.03, 0.4),           # 먹었어도 대사로 0 밑 — 꺼내기만
        (0.5, 0.03, 0.2),              # 문턱 아래 보통
    ]
    out = []
    for e_new, g, r in ins:
        e_out, r_out = reserve_once(w, e_new, g, r)
        out.append((e_new, g, r, e_out, r_out))
    return out


def starve_chain(w: World) -> tuple[int, list[tuple[int, float, float]]]:
    drain = w.cfg.energy_drain
    E, R = float(w.cfg.init_energy), float(w._wr["init"])
    samples = [(0, E, R)]
    t = 0
    while True:
        t += 1
        e_new = min(E - drain + 0.0, w.cfg.max_energy)
        w.reserve = np.full(w.N, R)
        E = float(w._wild_reserve_step(np.full(w.N, e_new), np.zeros(w.N), None)[0])
        R = float(w.reserve[0])
        if t % 100 == 0:
            samples.append((t, E, R))
        if E <= 0.0 and R <= 0.0:
            samples.append((t, E, R))
            return t, samples
        if t > 100000:
            raise SystemExit("굶음 열이 끝나지 않는다")


def mixed_chain(w: World, steps: int = 600) -> list[tuple[float, float]]:
    drain = w.cfg.energy_drain
    E, R = 0.2, 0.2
    out = []
    for t in range(steps):
        g = 0.03 if (t // 50) % 3 == 0 else 0.0
        e_new = min(E - drain + g, w.cfg.max_energy)
        w.reserve = np.full(w.N, R)
        E = float(w._wild_reserve_step(np.full(w.N, e_new), np.full(w.N, g), None)[0])
        R = float(w.reserve[0])
        out.append((E, R))
    return out


def satiation_chain(steps: int = 500) -> tuple[World, list[list[tuple[int, int, bool, float]]]]:
    w = World(load_v2_config(WILD).replace(N=N), seeds=[SEED + 1])
    w.reset()
    if w._ws is None:
        raise SystemExit("v3_wild1_mirror.yaml 의 wild_satiation 이 꺼졌다")
    w.pos[:] = [1.0, 1.0]
    w.pred_pos[:] = [30.0, 30.0]
    w.dark = 0.0
    w.pred_asleep[:] = False
    if getattr(w, "_zn", None) is not None:
        w._zn_act[:] = w._zn["ramp_steps"]
    w._pred_speed_mult = np.ones(w.M)
    w.pred_cd[:] = int(w.cfg.pred_eat_cd)
    w.pred_sat[:] = w._ws_sat_steps
    rows = []
    for _ in range(steps):
        w._step_predators_v3()
        rows.append([(int(w.pred_cd[m]), int(w.pred_sat[m]), bool(w.pred_sated[m]), float(np.hypot(*w.pred_vel[m])))
                     for m in range(w.M)])
    return w, rows


def build_header() -> str:
    w = make_world()
    wr = w._wr
    cases = reserve_cases(w)
    starve_t, starve = starve_chain(w)
    mixed = mixed_chain(w)
    ws_w, sat = satiation_chain()
    types = [int(t) for t in ws_w.pred_type]
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_wild.py (손으로 고치지 않는다). 세계 configs/v3_wild1_mirror.yaml, 시드 32090.",
        "// v3 야생 1단계 골든 (명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md 5절). 검사는 Tests/EcoWildV3Test.cpp (AdaptiveEcosystem.Policy.V3.Wild.*).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenWild",
        "{",
        "\t// (w1) wild_reserve 계수 (파이썬 World._wr) · 하루 스텝 · 대사 · 용량 C = reserve_days × dn_period × energy_drain",
        f"\tinline constexpr double kReserveDays = {d_lit(wr['reserve_days'])};",
        f"\tinline constexpr double kReserveInit = {d_lit(wr['init'])};",
        f"\tinline constexpr double kRefillE = {d_lit(wr['refill_e'])};",
        f"\tinline constexpr double kRefillFrac = {d_lit(wr['refill_frac'])};",
        f"\tinline constexpr double kWeakE = {d_lit(wr['weak_e'])};",
        f"\tinline constexpr double kWeakSpeed = {d_lit(wr['weak_speed'])};",
        f"\tinline constexpr std::int32_t kDayPeriod = {int(w.dn_period)};",
        f"\tinline constexpr double kEnergyDrain = {d_lit(w.cfg.energy_drain)};",
        f"\tinline constexpr double kInitEnergy = {d_lit(w.cfg.init_energy)};",
        f"\tinline constexpr double kMaxEnergy = {d_lit(w.cfg.max_energy)};",
        f"\tinline constexpr double kReserveCap = {d_lit(w._wr_cap)};",
        "",
        "\t// 비축 한 번: 행마다 e_new, 먹은 에너지, R → E, R",
        f"\tinline constexpr std::int32_t kReserveCaseCount = {len(cases)};",
        c_array("double", "kReserveCases", [v for c in cases for v in c], 5, d_lit),
        "",
        "\t// 굶음 열: 걷기 대사만, E 0.5·R 가득에서. 죽는 스텝과 (스텝, E, R) 표본 (100 스텝마다 + 죽는 스텝)",
        f"\tinline constexpr std::int32_t kStarveDeathStep = {starve_t};",
        f"\tinline constexpr std::int32_t kStarveSampleCount = {len(starve)};",
        c_array("std::int32_t", "kStarveSampleStep", [s[0] for s in starve], 12, str),
        c_array("double", "kStarveSampleE", [s[1] for s in starve], 6, d_lit),
        c_array("double", "kStarveSampleR", [s[2] for s in starve], 6, d_lit),
        "",
        "\t// 섞음 열: E 0.2·R 0.2 에서, 스텝 t 의 먹은 에너지 = 0.03 if (t / 50) % 3 == 0 else 0. 스텝마다 (E, R)",
        "\tinline constexpr double kMixedStartE = 0.2;",
        "\tinline constexpr double kMixedStartR = 0.2;",
        "\tinline constexpr double kMixedGain = 0.03;",
        f"\tinline constexpr std::int32_t kMixedSteps = {len(mixed)};",
        c_array("double", "kMixedER", [v for p in mixed for v in p], 6, d_lit),
        "",
        "	// (w2) wild_satiation: sat 스텝 = wild_days_to_steps(sat_days, dn_period), rest_speed, 먹기 쿨다운, 늑대 기본 속력",
        f"	inline constexpr double kSatDays = {d_lit(ws_w._ws['sat_days'])};",
        f"	inline constexpr double kRestSpeed = {d_lit(ws_w._ws['rest_speed'])};",
        f"	inline constexpr std::int32_t kSatSteps = {int(ws_w._ws_sat_steps)};",
        f"	inline constexpr std::int32_t kPredEatCd = {int(ws_w.cfg.pred_eat_cd)};",
        f"	inline constexpr double kPredBaseSpeed = {d_lit(ws_w.pred_speed[0])};   // 늑대 기본 속력 (단위/스텝, 0.6 × 0.8)",
        "	// 포만 열: 늑대 슬롯마다 종류 (0 추격형, 1 잠행형 — world.py PT_CHASER·PT_STALKER), 스텝마다 늑대마다 (쿨다운, 남은 배부름, 배부름 0/1, 변위 크기)",
        f"	inline constexpr std::int32_t kSatWolves = {len(types)};",
        c_array("std::int32_t", "kSatWolfType", types, 8, str),
        f"	inline constexpr std::int32_t kSatChainSteps = {len(sat)};",
        c_array("std::int32_t", "kSatChainInt", [v for r in sat for c in r for v in (c[0], c[1], int(c[2]))], 12, str),
        c_array("double", "kSatChainVel", [c[3] for r in sat for c in r], 6, d_lit),
        "}",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "WildGoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()
