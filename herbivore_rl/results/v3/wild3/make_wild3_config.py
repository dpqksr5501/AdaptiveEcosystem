"""야생 3단계 거울 설정 만들기 (10-18 사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘. 그리고 그 날씨와 장애물들을 바탕으로 만들어진 세계를
파이썬에 고대로 옮겨서 학습시킬 거야').

    # herbivore_rl/ 에서
    python results/v3/wild3/make_wild3_config.py           # configs/v3_wild3_mirror.yaml 을 쓴다
    python results/v3/wild3/make_wild3_config.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

configs/v3_wild3_mirror.yaml = 머리 주석 + configs/v3_wild2_trees_mirror.yaml 그대로(version 만 바꿈) + wild_weather 블록(train 앞).
나무 거울 설정은 results/v3/wild2/trees/make_tree_layout.py 가 만든다 — 그 파일이 바뀌면 이것도 다시 만든다(tests/test_wild3_weather.py 가 최신인지 본다).
정의·식은 env_v2/world.py 모듈 docstring '야생 3단계', 명세 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_WILD2_SPEC.md 11절, 결과 results/v3/wild3/README.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
TREES_YAML = ROOT / "configs" / "v3_wild2_trees_mirror.yaml"
YAML_OUT = ROOT / "configs" / "v3_wild3_mirror.yaml"

HEAD = """\
# 야생 3단계 거울 세계 — 팀 지역 날씨(숲 비·고지 눈·메마른 땅 맑음) + 무대 나무 (10-18 사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘. 그리고 그 날씨와
# 장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서 학습시킬 거야').
# 자동 생성 — results/v3/wild3/make_wild3_config.py (손으로 고치지 않는다. v3_wild2_trees_mirror.yaml 을 고치면 다시 만든다). 설명 results/v3/wild3/README.md,
# 명세 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_WILD2_SPEC.md 11절, 정의·식 env_v2/world.py 모듈 docstring '야생 3단계'.
# = configs/v3_wild2_trees_mirror.yaml(아래 그대로) + wild_weather 블록 하나(맨 끝, train 앞). 재기 전용 세계이고(부활 없음) 학습 세계는 이 위에 따로 만든다.
# 지역: 이 파일 하나만 쓰면 모든 세계가 숲 무대(숲 나무 원판 + 비)다. 짝 비교 실행기 run_mirror.py --unreal-maps … --unreal-obstacles
#   results/v3/wild2/trees/tree_layout.json 은 지도 (세션, 지역) 마다 그 지역 원판과 그 지역 날씨(wild_weather.region)를 덮는다.
# wild_weather 를 끄면(또는 모든 지역을 맑음으로 두면) v3_wild2_trees_mirror.yaml 과 비트 단위로 같다(tests/test_wild3_weather.py). 시드: 탐색 32000~32099·33000~33099 만.
#
# ── 아래는 v3_wild2_trees_mirror.yaml 그대로 (version 과 wild_weather 블록만 다르다) ──
"""

BLOCK = """\
  # ── 야생 3단계 지역 날씨 (10-18, 기능 31 — 정의·식·C++ 꼴은 env_v2/world.py 모듈 docstring '야생 3단계', 출처·어림은 명세 11절) ──────────────────────────
  # 팀 설계(LV_SHC_RegionalWeatherTest — 숲 트리거 상자 비, 고지 상자 눈, 메마른 땅 맑음, 세기는 비 타임라인 끝 값 1)를 지역마다 고정 날씨로 둔다.
  # 세기 I 의 배수 = 1 − (1 − 아래 값)·I. 맑음은 배수가 모두 1 이라 그 지역은 날씨 없는 세계와 비트 단위로 같다. 난수 없음. 관측 칸은 그대로다(visibility 가 시야 배수를 싣는다).
  wild_weather:
    enabled: true
    # 이 세계가 흉내 내는 지역(짝 비교 실행기가 지도마다 덮는다). 이 파일 하나만 쓰면 숲(나무 원판도 숲 표)
    region: Forest
    # 지역 → [날씨, 세기]. 팀 블루프린트: 숲 BP_SHC_RainRegionalWeather(Rain_System, 빗소리 음량 = 세기, 끝 값 1), 고지 BP_SHC_SnowRegionalWeather(NS_Blizzard — 세기를 따르지
    # 않고 늘 가득 내림), 메마른 땅 날씨 액터 없음
    regions:
      Barren: [clear, 0.0]
      Forest: [rain, 1.0]
      Highland: [snow, 1.0]
    # 비 시야 × 0.9(사슴 위협 탐지 반경 40 m → 36 m, 늑대 시야 28 m → 25.2 m). 현실 근거: 큰비 시정 약 2 km 에서 40 m 앞 빛 대비 손실은 약 6%(시정 정의
    # exp(−3 × 거리 ÷ 시정))이고, 빗줄기·젖은 잎 흔들림이 움직임을 가린다(나머지 몫은 어림)
    rain_sight: 0.9
    # 비 사슴 청각 × 0.5(달리는 늑대 발소리 40 m → 20 m, 살금살금 4 m → 2 m). 현실 근거: 빗소리가 배경 소음을 6 dB 올리면 구면 퍼짐에서 들리는 거리가 반이 된다
    # (Barber 외 2010 TREE 25:180 — 소음이 들리는 넓이를 줄인다). 숲의 빗소리는 그보다 크게 올린다고 보아 0.5 는 작게 잡은 값이다(어림). 늑대는 이 세계에서 눈으로만
    # 사슴을 찾아(청각 칸 없음) 청각 배수는 사슴에게만 걸린다
    rain_hear: 0.5
    # 눈 시야 × 0.7(40 m → 28 m, 늑대 28 m → 19.6 m). 현실 근거: 큰 눈은 시정 400 m 이하(Rasmussen 외 1999 J. Appl. Meteor. 38:1542 — 눈 세기를 시정으로 가른다)라
    # 40 m 앞 빛 대비가 exp(−0.3) = 0.74 로 준다. 팀 효과는 눈보라(NS_Blizzard)라 조금 더 낮춰 0.7(어림)
    snow_sight: 0.7
    # 눈 청각 그대로: 갓 내린 눈은 소리를 빨아들이지만 언 눈은 밟으면 뽀득거려 방향이 엇갈린다(R3 명세 지형 소리 줄과 같은 판단). 느려진 늑대는 저절로 덜 들린다
    snow_hear: 1.0
    # 눈 이동: 사슴 × 0.6, 늑대 × 0.85 — R3 지형 눈 값 그대로(H18, '발과 땅의 물리라 세계마다 바꾸지 않는다'). 현실 근거: 사슴은 발 하중이 늑대보다 커서 눈에 더
    # 빠지고(Telfer & Kelsall 1984 Ecology 65:1828), 눈이 깊을수록 늑대가 사슴을 더 잡는다(Nelson & Mech 1986 J. Wildl. Manage. 50:471, 미네소타 10년). 고지 무대 전체가
    # 눈이라 쫓는 늑대(0.8 × 0.85 = 0.68)가 뛰는 사슴(0.6)보다 빠르다 — 센 규칙이다(명세 11-4 세기 0.5 판도 잰다)
    snow_deer_speed: 0.6
    snow_wolf_speed: 0.85
    # 관측 visibility = (1 − 0.5·d) × 시야 배수(계획서 RL_V2_PLAN.md 4.2 표 9·#25 — 칸을 처음부터 이렇게 계약했다). 사슴은 이 칸으로 날씨를 안다
    obs_visibility: true
    # 시간에 따라 바뀌는 날씨의 자리(선택 키): null = 지역마다 늘 같다. 예 {Forest: [[0, rain, 1.0], [900, clear, 0.0]]}
    schedule: null

"""


def render() -> str:
    src = TREES_YAML.read_text(encoding="utf-8")
    if src.count('version: "3.wild2trees"') != 1 or src.count("\ntrain:\n") != 1:
        raise SystemExit("v3_wild2_trees_mirror.yaml 의 version·train 줄을 못 찾았다 — 생성기를 고친다")
    src = src.replace('version: "3.wild2trees"', 'version: "3.wild3"', 1)
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
