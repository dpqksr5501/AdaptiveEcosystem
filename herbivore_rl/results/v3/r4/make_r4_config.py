"""v3 R4 학습 세계 설정 만들기 (10-18 사용자 '그 날씨와 장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야', 사람 결정 RL_V2_PLAN.md 10-18 (15)).

    # herbivore_rl/ 에서
    python results/v3/r4/make_r4_config.py           # configs/v3_r4_train.yaml 을 쓴다
    python results/v3/r4/make_r4_config.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

configs/v3_r4_train.yaml = 머리 주석 + configs/v3_wild3_mirror.yaml 그대로 + 바꾼 곳 넷(그 밖의 줄은 한 글자도 바꾸지 않는다 — tests/test_r4_train.py 가 본다):
  1) version "3.wild3" → "3.r4"
  2) overrides.train_seeds [32000, 32050] (v1 [0, 1000) 대신 — 학습 세계 시드 풀. 탐색 32000~32099 의 앞 절반, 뒤 절반은 점검·고르기용)
  3) integrated_stage.respawn false → true + 선택 키 respawn_safe_r 20.0·respawn_tries 64 (학습 보충, 사람 결정 D2)
  4) train 블록 전체: 학습 값(R3 조리법 그대로, f_dec 는 이 세계에서 잰 값) + region_mix(지역 셋 같은 비율, 지역 나무 원판 = 배치 표 tree_layout.json)
배치 표(results/v3/wild2/trees/tree_layout.json)나 거울 설정이 바뀌면 다시 만든다. 사전 등록 results/v3/r4/PREREG.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
MIRROR = ROOT / "configs" / "v3_wild3_mirror.yaml"
LAYOUT = ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
YAML_OUT = ROOT / "configs" / "v3_r4_train.yaml"

# f_dec: `python train_v3.py measure-fdec --config configs/v3_r4_train.yaml --seeds 32000 32001 32002` (시작 정책 = 모델 시드 0 의 무작위 가중치 + 시작
# 로짓 편향, 지역 셋 × 시드 셋 × 3000스텝 — R1·R3 와 같은 정의). 기록 results/v3/r4/measure_fdec.log. ent_coef_base = 0.01 × f_dec (범주 엔트로피 계수 0.01)
F_DEC = 0.854956
REGIONS = ("Barren", "Forest", "Highland")
TRAIN_SEEDS = (32000, 32050)
SAFE_R = 20.0
TRIES = 64

HEAD = """\
# v3 R4 학습 세계 — 언리얼 통합 레벨과 같은 세계(지역마다 고정 배치 나무 + 지역 날씨)에서 게임 두뇌 R1b-F 를 이어 배운다 (10-18 사용자 '그 날씨와 장애물들을 바탕으로
# 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야', 사람 결정 AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md 10-18 (15) D1~D4, 사전 등록 results/v3/r4/PREREG.md).
# 자동 생성 — results/v3/r4/make_r4_config.py (손으로 고치지 않는다. v3_wild3_mirror.yaml·나무 배치 표가 바뀌면 다시 만든다).
# = configs/v3_wild3_mirror.yaml(판정 세계, 아래 그대로) + 바꾼 곳 넷:
#   1) version 3.r4
#   2) overrides.train_seeds [32000, 32050]: 학습 세계 시드 풀(파이썬 먹이 지도). 언리얼 C++ 먹이 지도와 만드는 식(균등 잡음 → 블러 → 정규화 → 문턱)이 같고 난수열만
#      다르다 — 분포가 같은 지도다. 32050~32099 는 학습에 쓰지 않는다(2M·5M 점검·게임 모델 고르기)
#   3) integrated_stage.respawn true + respawn_safe_r 20(40 m)·respawn_tries 64: 학습 보충(사람 결정 D2) — 죽은 사슴은 다음 스텝에 모든 늑대에게서 40 m 밖·나무
#      원판 밖·은신처 밖 자리에 다시 난다. 학습 장치이지 게임 규칙이 아니다(판정 세계·언리얼은 부활 없음 그대로)
#   4) train 블록: R3 조리법(세계 8·교체 5000·롤아웃 256·ε 0.05·목록 먹기·도망·숨기) + region_mix — 새 세계마다 지역 하나를 같은 비율로 뽑아 그 지역 날씨
#      (wild_weather.region)와 그 지역 나무 원판(obstacles.fixed — 배치 표 trees-1017a: 메마른 땅 0·숲 24·고지 9)으로 만든다(env_v2/vec_env.py)
# 아래 wild_weather.region·obstacles.fixed(숲)는 지역 섞기가 세계마다 덮는다. 이 파일을 World 하나로 바로 열면 숲 무대다.
# 판정·점검·고르기는 부활 없는 v3_wild3_mirror.yaml 에서 한다(results/v3/r4/r4_eval.py). 시드: 학습 32000~32049, 점검·고르기 32050~32099, 판정 33000~33099.
#
# ── 아래는 v3_wild3_mirror.yaml 그대로 (위 넷만 다르다) ──
"""


def train_block(layout: dict) -> str:
    regs = {r["region"]: r["discs"] for r in layout["regions"]}
    missing = [r for r in REGIONS if r not in regs]
    if missing:
        raise SystemExit(f"배치 표에 지역 {missing} 가 없다")
    lines = [
        "train:",
        "  # R4 학습(사전 등록 results/v3/r4/PREREG.md 3절). R3 조리법 그대로: 세계 8·교체 5000·롤아웃 256(train_v3.py), 시작 = R1b s3 가중치(--init-from-model)",
        "  num_worlds: 8",
        "  reset_interval: 5000",
        "  rollout_world_steps: 256",
        "  repertoire:",
        "    # 먹기·도망·숨기(얼기·잠 막음, 마스크 판 2). R1b 의 FREEZE 로짓은 남지만 마스크가 늘 막는다(R3 H13 과 같은 방식)",
        "    allowed: [graze, flee, hide]",
        "    epsilon: 0.05",
        "    init_probs: [0.4, 0.15, 0.15, 0.15, 0.15]",
        f"    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = 이 세계(지역 셋)에서 잰 시작 정책 결정 비율(results/v3/r4/measure_fdec.log)",
        f"    ent_coef_base: {round(0.01 * F_DEC, 8)!r}",
        f"    f_dec: {F_DEC!r}",
        "  # 지역 섞기(env_v2/vec_env.py 'v3 R4 지역 섞기'): 새 세계마다 지역 하나(같은 비율). 지역 = 날씨(features.wild_weather.regions 표) + 나무 원판(아래, 단위 x·y·r)",
        f"  # 원판 = 나무 배치 표 {layout['version']}(지문 {layout['digest']}, results/v3/wild2/trees/tree_layout.json) — 언리얼 통합 모드(eco.IntegratedV3.StageTrees 1)가 같은 표로 놓는다",
        "  region_mix:",
        f"    regions: [{', '.join(REGIONS)}]",
        "    weights: [1, 1, 1]",
        "    obstacles:",
    ]
    for r in REGIONS:
        if not regs[r]:
            lines.append(f"      {r}: []")
            continue
        lines.append(f"      {r}:")
        lines.extend(f"        - [{x!r}, {y!r}, {rad!r}]" for x, y, rad in regs[r])
    return "\n".join(lines) + "\n"


def render() -> str:
    src = MIRROR.read_text(encoding="utf-8")
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))

    def sub(old: str, new: str) -> None:
        nonlocal src
        if src.count(old) != 1:
            raise SystemExit(f"v3_wild3_mirror.yaml 에서 바꿀 줄을 하나로 못 찾았다: {old!r} — 생성기를 고친다")
        src = src.replace(old, new, 1)

    sub('version: "3.wild3"', 'version: "3.r4"')
    sub("  pred_eat_cd: 38\n",
        "  pred_eat_cd: 38\n"
        "  # R4 학습 세계 시드 풀 [시작, 끝) — 탐색 범위 32000~32099 의 앞 절반(뒤 절반은 점검·고르기). v1 은 [0, 1000)\n"
        f"  train_seeds: [{TRAIN_SEEDS[0]}, {TRAIN_SEEDS[1]}]\n")
    sub("    respawn: false\n",
        "    respawn: true\n"
        "    # (r) R4 학습 보충(사람 결정 D2): 죽은 사슴은 다음 스텝에 모든 늑대에게서 respawn_safe_r(20 단위 = 40 m — 도주 반사의 안전 거리 wild_flight.safe_r 를\n"
        "    # 빌린 값, 추정) 밖·원판 밖·은신처 밖 자리에 다시 난다. 후보 respawn_tries 개 가운데 처음 맞는 것, 없으면 늑대에게서 가장 먼 후보(env_v2/world.py\n"
        "    # _ist_safe_spawn). 학습 전용 — 판정 세계 v3_wild3_mirror.yaml 과 언리얼은 부활 없음\n"
        f"    respawn_safe_r: {SAFE_R!r}\n"
        f"    respawn_tries: {TRIES}\n")
    cut = src.index("\ntrain:\n")
    return HEAD + src[:cut + 1] + train_block(layout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    text = render()
    if a.check:
        ok = YAML_OUT.exists() and YAML_OUT.read_text(encoding="utf-8") == text
        print("최신이다" if ok else f"{YAML_OUT} 가 지금 규칙으로 만든 것과 다르다 — 다시 만든다")
        return 0 if ok else 1
    YAML_OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"-> {YAML_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
