"""v3 R5 학습 세계 설정 만들기 (10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 RL_V2_PLAN.md 10-19 (16) (c)).

    # herbivore_rl/ 에서
    python results/v3/r5/make_r5_config.py           # configs/v3_r5_train.yaml 을 쓴다
    python results/v3/r5/make_r5_config.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

configs/v3_r5_train.yaml = 머리 주석 + configs/v3_wild3_obs_mirror.yaml 그대로(R5 판정 세계 — 언리얼과 같은 세계 + 관측 21) + 바꾼 곳 넷
(그 밖의 줄은 한 글자도 바꾸지 않는다 — tests/test_r5_train.py 가 본다). R4 생성기(results/v3/r4/make_r4_config.py)와 같은 꼴이다:
  1) version "3.wild3obs" → "3.r5"
  2) overrides.train_seeds [32000, 32050] (R4 와 같은 학습 세계 시드 풀)
  3) integrated_stage.respawn false → true + respawn_safe_r 20.0(40 m)·respawn_tries 64 (R4 와 같은 학습 보충)
  4) train 블록 전체: R3·R4 조리법 그대로(f_dec 는 이 세계에서 잰 값) + region_mix(지역 셋 같은 비율, 지역 나무 원판 = 배치 표) + random_forest
     (세계의 절반은 지역 날씨에 무작위 밀도 숲 — env_v2/vec_env.py 모듈 docstring 'v3 R5 무작위 숲 섞기')
배치 표(results/v3/wild2/trees/tree_layout.json)나 관측 21 거울 설정이 바뀌면 다시 만든다. 사전 등록 results/v3/r5/PREREG.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
MIRROR = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"
LAYOUT = ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
YAML_OUT = ROOT / "configs" / "v3_r5_train.yaml"

# f_dec: `python train_v3.py measure-fdec --config configs/v3_r5_train.yaml --seeds 32000 32001 32002` (시작 정책 = 모델 시드 0 의 무작위 가중치 + 시작
# 로짓 편향, 지역 셋(언리얼 나무 원판) × 시드 셋 × 3000스텝 — R1·R3·R4 와 같은 정의, 무작위 숲 세계는 재지 않는다). 기록 results/v3/r5/logs/measure_fdec.log.
# ent_coef_base = 0.01 × f_dec (범주 엔트로피 계수 0.01 — train_v3.py 가 ent_coef_base ÷ f_dec 로 쓴다)
F_DEC = 0.858922
REGIONS = ("Barren", "Forest", "Highland")
TRAIN_SEEDS = (32000, 32050)
SAFE_R = 20.0
TRIES = 64
# 무작위 숲(사전 등록 1-1 표). 줄기·바위 = 무작위 배치 계수 그대로(configs 의 obstacles 블록 — 온대 성숙림 단면적 34 m²/ha 쪽), 덤불 = 적응 고리 dense 세계의
# 덤불(results/v3/adapt/adapt.py SHRUB_PER_HA·SHRUB_R). 밀도 u ~ U[0, 1] 이 셋 모두에 곱해진다 — u 0 이면 나무 없음, 1 이면 줄기 360 + 바위 7 (+ 덤불 216)
RANDOM_FOREST = dict(share=0.5, density=[0.0, 1.0], tree_per_ha=250.0, tree_r=[0.05, 0.15], rock_per_ha=5.0, rock_r=[0.25, 0.75],
                     brush_share=0.5, brush_per_ha=150.0, brush_r=[0.5, 1.0])

HEAD = """\
# v3 R5 학습 세계 — 관측 21(관측 18 + 장애물 세 칸)로 게임 두뇌 R1b-F 를 이어 배운다. 세계의 절반은 언리얼 통합 레벨과 같은 세계(지역 날씨 + 지역 나무 배치),
# 절반은 지역 날씨에 무작위 밀도 숲(나무 없음 ~ 빽빽한 줄기·덤불) (10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서
# AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md 10-19 (16) (c), 사전 등록 results/v3/r5/PREREG.md).
# 자동 생성 — results/v3/r5/make_r5_config.py (손으로 고치지 않는다. v3_wild3_obs_mirror.yaml·나무 배치 표가 바뀌면 다시 만든다).
# = configs/v3_wild3_obs_mirror.yaml(R5 판정 세계, 아래 그대로) + 바꾼 곳 넷:
#   1) version 3.r5
#   2) overrides.train_seeds [32000, 32050]: 학습 세계 시드 풀(R4 와 같다). 32050~32099 는 학습에 쓰지 않는다(2M·5M 점검·게임 모델 고르기)
#   3) integrated_stage.respawn true + respawn_safe_r 20(40 m)·respawn_tries 64: 학습 보충(R4 와 같다 — 판정 세계·언리얼은 부활 없음)
#   4) train 블록: R3·R4 조리법(세계 8·교체 5000·롤아웃 256·ε 0.05·목록 먹기·도망·숨기) + region_mix(R4 지역 섞기) + random_forest(R5 — 새 세계마다
#      절반 확률로 지역 나무 원판 대신 무작위 밀도 숲 원판, env_v2/vec_env.py 'v3 R5 무작위 숲 섞기')
# 판정·점검·고르기는 부활 없는 언리얼 세계(관측 21 두뇌는 v3_wild3_obs_mirror.yaml, 관측 18 두뇌 R1b-F 는 v3_wild3_mirror.yaml — 세계는 비트 단위로 같다)에서
# 한다(results/v3/r5/r5_eval.py). 시드: 학습 32000~32049, 점검·고르기 32050~32079, 스모크 32080~32099, 판정 33100~33199.
#
# ── 아래는 v3_wild3_obs_mirror.yaml 그대로 (위 넷만 다르다) ──
"""


def train_block(layout: dict) -> str:
    regs = {r["region"]: r["discs"] for r in layout["regions"]}
    missing = [r for r in REGIONS if r not in regs]
    if missing:
        raise SystemExit(f"배치 표에 지역 {missing} 가 없다")
    rf = RANDOM_FOREST
    lines = [
        "train:",
        "  # R5 학습(사전 등록 results/v3/r5/PREREG.md 3절). R3·R4 조리법 그대로: 세계 8·교체 5000·롤아웃 256(train_v3.py),",
        "  # 시작 = R1b s3 가중치 + 새 세 칸 입력 열 0(ckpt/v3/v3_r1_g995_s3_obs21zero.zip, results/v3/r5/zero_extend.py — --init-from-model)",
        "  num_worlds: 8",
        "  reset_interval: 5000",
        "  rollout_world_steps: 256",
        "  repertoire:",
        "    # 먹기·도망·숨기(얼기·잠 막음, 마스크 판 2). R1b 의 FREEZE 로짓은 남지만 마스크가 늘 막는다(R3 H13·R4 와 같은 방식)",
        "    allowed: [graze, flee, hide]",
        "    epsilon: 0.05",
        "    init_probs: [0.4, 0.15, 0.15, 0.15, 0.15]",
        "    # 범주 엔트로피 계수 = ent_coef_base ÷ f_dec = 0.01. f_dec = 이 세계(지역 셋, 언리얼 나무 원판)에서 잰 시작 정책 결정 비율(results/v3/r5/logs/measure_fdec.log)",
        f"    ent_coef_base: {round(0.01 * F_DEC, 8)!r}",
        f"    f_dec: {F_DEC!r}",
        "  # 지역 섞기(env_v2/vec_env.py 'v3 R4 지역 섞기'): 새 세계마다 지역 하나(같은 비율). 지역 = 날씨(features.wild_weather.regions 표) + 나무 원판(아래, 단위 x·y·r)",
        f"  # 원판 = 나무 배치 표 {layout['version']}(지문 {layout['digest']}, results/v3/wild2/trees/tree_layout.json) — 언리얼 통합 모드(eco.IntegratedV3.StageTrees 1)가 같은 표로 놓는다",
        "  region_mix:",
        f"    regions: [{', '.join(REGIONS)}]",
        "    weights: [1, 1, 1]",
        "    # 무작위 숲 섞기(env_v2/vec_env.py 'v3 R5 무작위 숲 섞기'): 지역을 고른 뒤 share 확률로 그 세계의 원판을 아래 obstacles 대신 무작위 밀도 숲으로 바꾼다",
        "    # (날씨는 고른 지역 그대로). 밀도 u ~ U[density] 가 줄기·바위·덤불 수에 곱해진다(무대 1.44 ha — u 1 이면 줄기 360·바위 7, 덤불이면 + 216).",
        "    # 줄기 반지름 10~30 cm·1 ha 250 그루 = obstacles 블록 무작위 배치 계수(온대 성숙림 단면적 쪽), 바위 = 같은 블록, 덤불 반지름 1~2 m·1 ha 150 개 =",
        "    # 적응 고리 dense 세계의 덤불(results/v3/adapt/adapt.py). 까닭: 사용자 동기는 시간에 따라 바뀌는 식생이고 언리얼 레벨만으로는 나무가 적다(사전 등록 1-1)",
        "    random_forest:",
        f"      share: {rf['share']!r}",
        f"      density: [{rf['density'][0]!r}, {rf['density'][1]!r}]",
        f"      tree_per_ha: {rf['tree_per_ha']!r}",
        f"      tree_r: [{rf['tree_r'][0]!r}, {rf['tree_r'][1]!r}]",
        f"      rock_per_ha: {rf['rock_per_ha']!r}",
        f"      rock_r: [{rf['rock_r'][0]!r}, {rf['rock_r'][1]!r}]",
        f"      brush_share: {rf['brush_share']!r}",
        f"      brush_per_ha: {rf['brush_per_ha']!r}",
        f"      brush_r: [{rf['brush_r'][0]!r}, {rf['brush_r'][1]!r}]",
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
            raise SystemExit(f"v3_wild3_obs_mirror.yaml 에서 바꿀 줄을 하나로 못 찾았다: {old!r} — 생성기를 고친다")
        src = src.replace(old, new, 1)

    sub('version: "3.wild3obs"', 'version: "3.r5"')
    sub("  pred_eat_cd: 38\n",
        "  pred_eat_cd: 38\n"
        "  # R5 학습 세계 시드 풀 [시작, 끝) — 탐색 범위 32000~32099 의 앞 절반(뒤 절반은 점검·고르기·스모크, R4 와 같다). v1 은 [0, 1000)\n"
        f"  train_seeds: [{TRAIN_SEEDS[0]}, {TRAIN_SEEDS[1]}]\n")
    sub("    respawn: false\n",
        "    respawn: true\n"
        "    # (r) R5 학습 보충(R4 사람 결정 D2 그대로): 죽은 사슴은 다음 스텝에 모든 늑대에게서 respawn_safe_r(20 단위 = 40 m — 도주 반사의 안전 거리\n"
        "    # wild_flight.safe_r 를 빌린 값, 추정) 밖·원판 밖·은신처 밖 자리에 다시 난다. 후보 respawn_tries 개 가운데 처음 맞는 것, 없으면 늑대에게서 가장 먼\n"
        "    # 후보(env_v2/world.py _ist_safe_spawn). 학습 전용 — 판정 세계 v3_wild3_obs_mirror.yaml 과 언리얼은 부활 없음\n"
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
