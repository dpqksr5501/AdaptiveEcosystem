"""R5 장애물 관측 거울 설정 만들기 (10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 RL_V2_PLAN.md 10-19 (16)).

    # herbivore_rl/ 에서
    python results/v3/r5/make_obs_config.py           # configs/v3_wild3_obs_mirror.yaml 을 쓴다
    python results/v3/r5/make_obs_config.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

configs/v3_wild3_obs_mirror.yaml = 머리 주석 + configs/v3_wild3_mirror.yaml 그대로(version 만 바꿈) + obstacle_obs 블록(train 앞).
세계(이동·시선·먹이·늑대·날씨·난수)는 v3_wild3_mirror.yaml 과 같고 관측만 18 → 21 칸이다(앞 18 칸은 비트 단위로 같다 — tests/test_obstacle_obs.py).
R5 판정 세계(1차)가 이 설정이다. 거울 설정은 results/v3/wild3/make_wild3_config.py 가 만든다 — 그 파일이 바뀌면 이것도 다시 만든다(시험이 최신인지 본다).
정의·식은 env_v2/world.py 모듈 docstring 'R5 장애물 관측', 계약 AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
WILD3_YAML = ROOT / "configs" / "v3_wild3_mirror.yaml"
YAML_OUT = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"
ESCAPE_NORM = 10.0
NEAR_NORM = 5.0

HEAD = """\
# R5 장애물 관측 거울 세계 — 언리얼 통합 레벨과 같은 세계(지역 날씨 + 무대 나무)에 두뇌가 나무를 알아채는 관측 세 칸을 더한다 (10-19 사용자 '일단 두뇌가
# 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md 10-19 (16)).
# 자동 생성 — results/v3/r5/make_obs_config.py (손으로 고치지 않는다. v3_wild3_mirror.yaml 이 바뀌면 다시 만든다). 분포 확인 results/v3/r5/obs_check.md,
# 계약 AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4, 정의·식 env_v2/world.py 모듈 docstring 'R5 장애물 관측'.
# = configs/v3_wild3_mirror.yaml(아래 그대로) + obstacle_obs 블록 하나(맨 끝, train 앞). 세계는 그대로이고 관측만 18 → 21 칸이다(앞 18 칸은 비트 단위로 같다).
# 재기 전용 세계(부활 없음) — R5 판정 세계(1차). 지역: 이 파일 하나만 쓰면 숲 무대다(지역 덮기는 r4_eval.py 와 같은 두 칸).
# 시드: 탐색 32000~32099 · R5 판정 33100~33199 만.
#
# ── 아래는 v3_wild3_mirror.yaml 그대로 (version 과 obstacle_obs 블록만 다르다) ──
"""

BLOCK = f"""\
  # ── R5 장애물 관측 (10-19, 기능 32 — 정의·식·C++ 꼴은 env_v2/world.py 모듈 docstring 'R5 장애물 관측', 계약 2-4) ──────────────────────────────────────────
  # 관측 맨 끝 세 칸: escape_room(도망칠 쪽 — 위협을 알면 가장 가까운 위협 반대, 모르면 heading — 으로 곧장 갈 때 처음 막히는 원판(반지름 + 몸)·무대 벽까지 거리),
  # obstacle_near(몸 가장자리에서 가장 가까운 원판 가장자리까지), threat_hidden(가장 가까운 위협에서 나까지 눈길을 줄기가 가리면 1). 난수 없음, 세계 규칙 없음.
  obstacle_obs:
    enabled: true
    # escape_room 분모: {ESCAPE_NORM} 단위 = {ESCAPE_NORM * 2:.0f} m (뛰는 사슴 약 2 초 — 이보다 멀리 트였으면 1). 분포 확인 results/v3/r5/obs_check.md
    escape_norm: {ESCAPE_NORM}
    # obstacle_near 분모: {NEAR_NORM} 단위 = {NEAR_NORM * 2:.0f} m (곁에 줄기가 없으면 1)
    near_norm: {NEAR_NORM}

"""


def render() -> str:
    src = WILD3_YAML.read_text(encoding="utf-8")
    if src.count('version: "3.wild3"') != 1 or src.count("\ntrain:\n") != 1:
        raise SystemExit("v3_wild3_mirror.yaml 의 version·train 줄을 못 찾았다 — 생성기를 고친다")
    src = src.replace('version: "3.wild3"', 'version: "3.wild3obs"', 1)
    if not src.endswith("\n"):
        src += "\n"
    head, _, tail = src.partition("\ntrain:\n")
    head = head.rstrip("\n") + "\n\n"
    return HEAD + head + BLOCK + "train:\n" + tail


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="쓰지 않고 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다")
    a = ap.parse_args(argv)
    text = render()
    if a.check:
        if not YAML_OUT.exists() or YAML_OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"지금 규칙으로 만든 것과 다르다: {YAML_OUT}")
        print(f"최신: {YAML_OUT}")
        return
    YAML_OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"-> {YAML_OUT}")


if __name__ == "__main__":
    sys.exit(main())
