"""v3 야생 2단계 골든 내보내기 — 은신처 먹이 부족(realism_cover_food)과 사냥 성공률 셈(hunt_update)을 언리얼 C++ `EcoWorldV3.h` 와 대조할
골든 헤더를 만든다 (명세 `Docs/RL_Policy/RL_V3_WILD2_SPEC.md` '골든 시험').

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_wild2.py
    # 시험용 다른 폴더
    python export_golden_v3_wild2.py --out <폴더>

세계·시드:
  - 세계: configs/v3_wild2_mirror.yaml(은신처 먹이 부족 켬)과 같은 시드의 configs/v3_wild1_mirror.yaml(끔 — 1단계 용량 cap0). 탐색 시드 32090 하나.
  - 난수 장면: 이 내보내기 전용 탐색 시드 32091(겹침 장면)·32092(사냥 열). 판정 시드는 쓰지 않는다.
  - C++ 와 파이썬은 난수열이 달라 먹이 지도가 다르다. 그래서 파이썬 1단계 용량(cap0)을 그대로 싣고, C++ 은 그 용량·같은 은신처 원에서
    FFoodGrid::BuildCoverCells → ApplyShelterFood 를 불러 같은 값을 내야 한다(통합 모드 Build 와 같은 순서).

묶음:
  은신처 먹이  거울 세계(무대 60, 셀 2, 30 × 30, 은신처 4)의 cap0·셀 중심 은신처 셀(v1 cover_cell)·겹치는 셀(cover_food_cell)·새 용량·재생률.
  겹침 장면    작은 격자(한 변 10·11 셀, 셀 2)에 원 1~3개. 손 장면 6개(셀 경계에 꼭 닿는 원, 셀 모서리 중심, 대각선으로 모서리에 닿는 원, 맵 가장자리,
              겹친 두 원, 큰 원) + 난수 장면 10개. 셀 중심 마스크와 겹침 마스크(`World._cover_overlap_cells`). 반경 0 원은 넣지 않는다 — 파이썬
              세계에는 없고(C++ 통합 모드의 지워진 은신처만 반경 0) C++ 은 건너뛴다.
  사냥 열      늑대 5마리 × 400 스텝의 (전력 걸음, 잡음) 열(전력 걸음은 이어지기 쉬운 마르코프 열, 잡음은 전력 걸음일 때 4%·아닐 때 1%)을 `hunt_update`
              로 셈. 스텝·늑대마다 (on, 시작, 끝, 성공, 사냥 밖) 비트와 합.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from env_v2.config import load_v2_config
from env_v2.world import World, hunt_update

HERE = Path(__file__).resolve().parent
WILD1 = HERE / "configs" / "v3_wild1_mirror.yaml"
WILD2 = HERE / "configs" / "v3_wild2_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED = 32090
SEED_SCENES = 32091
SEED_HUNT = 32092
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


def u8(v) -> str:
    return str(int(v))


def food_world():
    """같은 시드의 1단계(끔)·2단계(켬) 세계. 은신처 원·1단계 용량이 같아야 한다."""
    w1 = World(load_v2_config(WILD1).replace(N=N), seeds=[SEED])
    w2 = World(load_v2_config(WILD2).replace(N=N), seeds=[SEED])
    if w2._zf is None or w1._zf is not None:
        raise SystemExit("v3_wild2_mirror.yaml 의 realism_cover_food 가 켜져 있고 v3_wild1_mirror.yaml 은 꺼져 있어야 한다")
    if not (np.array_equal(w1.cov_c, w2.cov_c) and np.array_equal(w1.cov_r, w2.cov_r)):
        raise SystemExit("두 세계의 은신처 원이 다르다")
    if not np.array_equal(w2.food_cap, np.where(w2.cover_food_cell, w1.food_cap * w2.cover_food_cap, w1.food_cap)):
        raise SystemExit("2단계 용량이 1단계 용량 × 배수가 아니다")
    return w1, w2


def overlap_scenes():
    """겹침 장면 (모듈 docstring '겹침 장면'). 장면마다 (격자 한 변, 원 목록 [(x, y, r)], 셀 중심 마스크, 겹침 마스크)."""
    w = World(load_v2_config(WILD2).replace(N=4), seeds=[SEED])
    c = float(w.cfg.food_cell)
    hand = [
        (10, [(5.0, 5.0, 1.0)]),                                 # 셀 경계 x = 4·6, y = 4·6 에 꼭 닿는 원
        (10, [(4.0, 4.0, 2.0)]),                                 # 셀 모서리가 중심
        (10, [(3.0, 7.0, math.sqrt(8.0))]),                      # 대각선으로 셀 모서리 (1, 5)·(5, 9) 에 닿는 원
        (10, [(0.5, 19.5, 1.5)]),                                # 맵 가장자리 원
        (11, [(8.0, 8.0, 3.0), (11.0, 9.5, 2.5)]),              # 겹친 두 원
        (11, [(11.0, 11.0, 9.0)]),                               # 큰 원
    ]
    rng = np.random.default_rng(SEED_SCENES)
    rand = []
    for _ in range(10):
        g = int(rng.integers(10, 12))
        k = int(rng.integers(1, 4))
        discs = [(float(rng.uniform(-1.0, g * c + 1.0)), float(rng.uniform(-1.0, g * c + 1.0)), float(rng.uniform(0.3, 6.0)))
                 for _ in range(k)]
        rand.append((g, discs))
    out = []
    for g, discs in hand + rand:
        w.gw = g
        cc = (np.arange(g) + 0.5) * c
        cx, cy = np.meshgrid(cc, cc)
        w.cov_c = np.asarray([d[:2] for d in discs], dtype=np.float64).reshape(-1, 2)
        w.cov_r = np.asarray([d[2] for d in discs], dtype=np.float64)
        mask = np.zeros((g, g), dtype=bool)
        for (px, py), r in zip(w.cov_c, w.cov_r):
            mask |= (cx - px) ** 2 + (cy - py) ** 2 <= r * r          # world._build_world 셀 중심 식
        w.cover_cell = mask
        over = w._cover_overlap_cells()
        out.append((g, discs, mask, over))
    return out, len(hand)


def hunt_chain(m: int = 5, steps: int = 400):
    """사냥 열 (모듈 docstring '사냥 열'). 반환 (전력 걸음 (T, M), 잡음 (T, M), 비트 (T, M), 합 [시작, 끝, 성공, 사냥 밖])."""
    rng = np.random.default_rng(SEED_HUNT)
    run = np.zeros((steps, m), dtype=bool)
    got = np.zeros((steps, m), dtype=bool)
    prev = np.zeros(m, dtype=bool)
    for t in range(steps):
        u = rng.random(m)
        run[t] = np.where(prev, u < 0.85, u < 0.12)
        got[t] = rng.random(m) < np.where(run[t], 0.04, 0.01)
        prev = run[t]
    on = np.zeros(m, dtype=bool)
    bits = np.zeros((steps, m), dtype=np.int64)
    tot = np.zeros(4, dtype=np.int64)
    for t in range(steps):
        on, start, end, success, outside = hunt_update(on, run[t], got[t])
        bits[t] = on.astype(np.int64) | (start << 1) | (end << 2) | (success << 3) | (outside << 4)
        tot += [int(start.sum()), int(end.sum()), int(success.sum()), int(outside.sum())]
    return run, got, bits, tot


def build_header() -> str:
    w1, w2 = food_world()
    zf = w2._zf
    scenes, n_hand = overlap_scenes()
    run, got, bits, tot = hunt_chain()
    T, M = run.shape
    g = w2.gw
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_wild2.py (손으로 고치지 않는다). 세계 configs/v3_wild2_mirror.yaml·v3_wild1_mirror.yaml, 시드 32090.",
        "// v3 야생 2단계 골든 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md '골든 시험'). 검사는 Tests/EcoWild2V3Test.cpp (AdaptiveEcosystem.Policy.V3.Wild2.*).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenWild2",
        "{",
        "\t// ---- 1 은신처 먹이 부족 (world.py realism_cover_food — 모듈 docstring (e)) ----",
        "\t// 계수 (World._zf)와 먹이 격자 상수 (configs/default.yaml 위 거울 설정)",
        f"\tinline constexpr double kCapFrac = {d_lit(zf['cap_frac'])};",
        f"\tinline constexpr double kRegenFrac = {d_lit(zf['regen_frac'])};",
        f"\tinline constexpr double kFoodRegenBase = {d_lit(w2.cfg.food_regen_base)};",
        f"\tinline constexpr double kFoodRegenMult = {d_lit(w2.food_regen_mult)};",
        f"\tinline constexpr double kFoodCoverRegenMult = {d_lit(w2.cfg.food_cover_regen_mult)};",
        f"\tinline constexpr double kFoodCell = {d_lit(w2.cfg.food_cell)};",
        "\t// 거울 세계: 무대 한 변·격자·은신처 원 (x, y, r) × kCoverCount. 셀 k = y·Gw + x (행 우선 — C++ FFoodGrid 와 같다)",
        f"\tinline constexpr double kWorldSize = {d_lit(w2.size)};",
        f"\tinline constexpr std::int32_t kGw = {g};",
        f"\tinline constexpr std::int32_t kCoverCount = {len(w2.cov_r)};",
        c_array("double", "kCover", [v for c, r in zip(w2.cov_c, w2.cov_r) for v in (c[0], c[1], r)], 6, d_lit),
        "\t// 1단계 용량 cap0 (은신처 먹이 부족 전), 셀 중심 은신처 셀(v1 cover_cell), 겹치는 셀(cover_food_cell), 새 용량, 새 재생률",
        c_array("double", "kCap0", w1.food_cap.ravel().tolist(), 6, d_lit),
        c_array("std::uint8_t", "kCoverCell", w2.cover_cell.ravel().astype(int).tolist(), 30, u8),
        c_array("std::uint8_t", "kCoverFoodCell", w2.cover_food_cell.ravel().astype(int).tolist(), 30, u8),
        c_array("double", "kCap", w2.food_cap.ravel().tolist(), 6, d_lit),
        c_array("double", "kRegen", w2.regen_field.ravel().tolist(), 6, d_lit),
        f"\tinline constexpr std::int32_t kCoverFoodCells = {int(w2.cover_food_cell.sum())};",
        f"\tinline constexpr std::int32_t kCoverCenterCells = {int(w2.cover_cell.sum())};",
        "",
        "\t// 겹침 장면: 장면 s 의 격자 한 변 kSceneGw[s], 원 kSceneDiscCount[s] 개 (kSceneDisc 에서 kSceneDiscStart[s] 부터 (x, y, r)),",
        "\t// 셀 중심 마스크·겹침 마스크 (kSceneMaskStart[s] 부터 Gw² 칸). 앞 kSceneHand 개는 손 장면",
        f"\tinline constexpr std::int32_t kScenes = {len(scenes)};",
        f"\tinline constexpr std::int32_t kSceneHand = {n_hand};",
    ]
    gws, counts, dstart, mstart, discs, centers, overs = [], [], [], [], [], [], []
    for sg, sd, mask, over in scenes:
        gws.append(sg)
        counts.append(len(sd))
        dstart.append(len(discs) // 3)
        mstart.append(len(centers))
        discs += [v for d in sd for v in d]
        centers += mask.ravel().astype(int).tolist()
        overs += over.ravel().astype(int).tolist()
    L += [
        c_array("std::int32_t", "kSceneGw", gws, 16, str),
        c_array("std::int32_t", "kSceneDiscCount", counts, 16, str),
        c_array("std::int32_t", "kSceneDiscStart", dstart, 16, str),
        c_array("std::int32_t", "kSceneMaskStart", mstart, 16, str),
        c_array("double", "kSceneDisc", discs, 6, d_lit),
        c_array("std::uint8_t", "kSceneCenter", centers, 40, u8),
        c_array("std::uint8_t", "kSceneOverlap", overs, 40, u8),
        "",
        "\t// ---- 사냥 성공률 셈 (world.py hunt_update — 모듈 docstring '야생 2단계') ----",
        "\t// 늑대 kHuntM 마리 × kHuntT 스텝. 칸 t·M + m: 전력 걸음, 잡음, 비트 (on | 시작 << 1 | 끝 << 2 | 성공 << 3 | 사냥 밖 << 4)",
        f"\tinline constexpr std::int32_t kHuntM = {M};",
        f"\tinline constexpr std::int32_t kHuntT = {T};",
        c_array("std::uint8_t", "kHuntRun", run.ravel().astype(int).tolist(), 40, u8),
        c_array("std::uint8_t", "kHuntCaught", got.ravel().astype(int).tolist(), 40, u8),
        c_array("std::uint8_t", "kHuntBits", bits.ravel().tolist(), 40, u8),
        "\t// 합 [시작, 끝, 성공, 사냥 밖]",
        c_array("std::int64_t", "kHuntTotals", tot.tolist(), 4, str),
        "}",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "Wild2GoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()
