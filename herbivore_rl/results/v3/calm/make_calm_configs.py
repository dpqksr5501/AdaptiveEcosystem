"""10-27 사용자 보고 두 고침의 설정 셋 만들기 — 먹기 걷기 고침(repertoire.graze_*)·거리 두기(쉬는 늑대, wild_flight.rest_keep*) 를 켠 세계
(사용자 10-27 '평소 사슴이 갈 곳을 못 정하고 방향만 왔다갔다 하며 제자리에서 미친 듯이 돈다'·'늑대가 쉬고 있어도 아주 잘 보이는 데서 사슴이 멈춰 있는 게
이상하다 — 늑대 시야 밖까지 물러난 뒤 쉬게'. 정의·식은 env_v2/repertoire.py `graze_calm_dir`·env_v2/world.py 모듈 docstring '거리 두기(쉬는 늑대)',
설계 AdaptiveEcosystem/Docs/RL_Policy/RL_V3_WILD1_SPEC.md 13절).

    # herbivore_rl/ 에서
    python results/v3/calm/make_calm_configs.py           # 아래 세 파일을 쓴다
    python results/v3/calm/make_calm_configs.py --check   # 올려 둔 파일이 지금 규칙으로 만든 것과 같은지만 본다 (쓰지 않는다)

세 파일 (그 밖의 줄은 한 글자도 바꾸지 않는다 — tests/test_calm_v3.py 가 YAML 로 읽어 바꾼 칸만 다른지 본다). 바꾼 곳은 모두 셋:
  1) version 뒤에 'calm'
  2) features.repertoire 끝(obs_extra 뒤)에 graze_edge_r 2.0 · graze_edge_w 2.5 · graze_inertia 0.5 · graze_wall_margin 1.0
  3) features.wild_flight 의 edge_r 뒤에 rest_keep true · rest_keep_margin 2.0 · rest_keep_band 4.0 · rest_keep_asleep false
  configs/v3_wild3_calm_mirror.yaml         = configs/v3_wild3_mirror.yaml(언리얼 통합 v3 기본값의 거울 — 내장 R1b-F, 관측 18) + 위 셋.
                                              언리얼 게임 기본(eco.IntegratedV3.GrazeCalm·RestKeep 1)의 거울이다.
  configs/v3_wild3_route5_calm_mirror.yaml  = configs/v3_wild3_route5_mirror.yaml(R7 판정 거울 — 두 길 두뇌 R7e, 관측 24·마스크 판 5) + 위 셋.
  configs/v3_r7_calm_train.yaml             = configs/v3_r7_train.yaml(R7 학습 세계) + 위 셋. 다음 학습부터 학습 세계와 게임 세계를 같게 하려는 판이다.
                                              train.repertoire f_dec·ent_coef_base 는 R7 값 그대로다 — 이 세계로 학습하기 전에 train_v3.py measure-fdec 로 다시 잰다.
값(시제품 scratch proto.py, 지도 12 × 탐색 시드 두 벌 — 설계 13절): 가장자리 2 단위(4 m)·무게 2.5·관성 0.5·벽 여유 1 단위(2 m), 거리 두기 여유 2 단위(4 m)·
띠 4 단위(8 m). 자는 늑대는 넣지 않는다(굴에 있어 안 보인다는 세계 규칙과 어긋나고, 넣으면 벽 밖 뒤집힘이 늘었다).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
CONFIGS = ROOT / "configs"

GRAZE = {"graze_edge_r": 2.0, "graze_edge_w": 2.5, "graze_inertia": 0.5, "graze_wall_margin": 1.0}
REST = {"rest_keep": True, "rest_keep_margin": 2.0, "rest_keep_band": 4.0, "rest_keep_asleep": False}

GRAZE_ANCHOR = "    obs_extra: true\n"
GRAZE_LINES = (
    "    # 10-27 먹기 걷기 고침(선택 키 — env_v2/features.py OPTIONAL_KEYS, 0 = 그대로. env_v2/repertoire.py `graze_calm_dir`): 먹이가 모자라 걷는\n"
    "    # 평소 GRAZE(경계·거리 두기 걷기 말고) 방향에 무대 가장자리 2(4 m) 안 되돌림(무게 2.5)·이번 이동 전 heading 관성 0.5 를 더하고, 벽 1(2 m) 안에서는\n"
    "    # 벽 쪽 성분을 지운다 — 무대 벽에 붙어 방향만 뒤집으며 제자리에서 도는 것을 막는다. 언리얼 eco.IntegratedV3.GrazeCalm 1(기본)\n"
    "    graze_edge_r: 2.0\n"
    "    graze_edge_w: 2.5\n"
    "    graze_inertia: 0.5\n"
    "    graze_wall_margin: 1.0\n")
REST_ANCHOR = "    edge_r: 5.0\n"
REST_LINES = (
    "    # 10-27 거리 두기(쉬는 늑대)(선택 키 — false = 그대로. env_v2/world.py 모듈 docstring '거리 두기'): 먹거나 배불러 쉬는 깨어 있는 늑대의 시야\n"
    "    # 반경(28 m × 날씨) 안에서 그 늑대를 알아챈 사슴은 걸어서 시야 + 2(4 m) 밖까지 물러난 뒤 쉬고(덮기 4 — 두뇌가 먹기일 때), 그 밖 4(8 m) 띠에서는\n"
    "    # 그 늑대 쪽으로 풀을 뜯어 다가가지 않는다. 켜면 rest_alert 의 쉬는 늑대 경계는 쓰지 않는다. 자는 늑대는 넣지 않는다. 언리얼 eco.IntegratedV3.RestKeep 1(기본)\n"
    "    rest_keep: true\n"
    "    rest_keep_margin: 2.0\n"
    "    rest_keep_band: 4.0\n"
    "    rest_keep_asleep: false\n")

HEAD_MIRROR = """\
# 10-27 고침 거울 세계 — 언리얼 통합 v3 기본값의 거울(v3_wild3_mirror.yaml)에 먹기 걷기 고침·거리 두기(쉬는 늑대)를 켠다 (10-27 사용자 '평소 사슴이 갈 곳을
# 못 정하고 방향만 왔다갔다 하며 제자리에서 미친 듯이 돈다'·'늑대가 쉬고 있어도 잘 보이는 데서 사슴이 멈춰 있다 — 늑대 시야 밖까지 물러난 뒤 쉬게').
# 자동 생성 — results/v3/calm/make_calm_configs.py (손으로 고치지 않는다. v3_wild3_mirror.yaml 이 바뀌면 다시 만든다).
# = configs/v3_wild3_mirror.yaml(아래 그대로) + 바꾼 곳 셋: version 3.wild3calm, features.repertoire.graze_*, features.wild_flight.rest_keep*.
#   두 규칙을 끄면(graze_* 0·rest_keep false) v3_wild3_mirror.yaml 과 비트 단위로 같다(tests/test_calm_v3.py). 관측·행동 계약은 그대로다(관측 18).
# 재기 전용 세계(부활 없음) — 언리얼 게임 기본(eco.IntegratedV3.GrazeCalm·RestKeep 1, 내장 R1b-F)의 짝 비교 거울. 시드: 탐색 32000~32099·33000~33099 만.
#
# ── 아래는 v3_wild3_mirror.yaml 그대로 (version 과 두 블록의 새 칸만 다르다) ──
"""
HEAD_ROUTE5 = """\
# 10-27 고침 R7 판정 거울 세계 — 두 길 두뇌 거울(v3_wild3_route5_mirror.yaml — 관측 24·마스크 판 5, R7e)에 먹기 걷기 고침·거리 두기(쉬는 늑대)를 켠다
# (10-27 사용자 보고 두 가지 — v3_wild3_calm_mirror.yaml 머리 주석).
# 자동 생성 — results/v3/calm/make_calm_configs.py (손으로 고치지 않는다. v3_wild3_route5_mirror.yaml 이 바뀌면 다시 만든다).
# = configs/v3_wild3_route5_mirror.yaml(아래 그대로) + 바꾼 곳 셋: version 3.wild3route5calm, features.repertoire.graze_*, features.wild_flight.rest_keep*.
#   계약(관측 24·판 5)은 그대로다 — 두 규칙은 두뇌가 고르는 칸이 아니다(거리 두기는 덮기가 아니라 경계와 같은 꼴이라 두뇌가 그대로 결정한다).
# 재기 전용 세계(부활 없음) — R7e 두뇌를 게임 기본(eco.IntegratedV3.GrazeCalm·RestKeep 1)으로 걸었을 때의 짝 비교 거울.
#
# ── 아래는 v3_wild3_route5_mirror.yaml 그대로 (version 과 두 블록의 새 칸만 다르다) ──
"""
HEAD_TRAIN = """\
# 10-27 고침 R7 학습 세계 — R7 학습 세계(v3_r7_train.yaml)에 먹기 걷기 고침·거리 두기(쉬는 늑대)를 켠다 (10-27 사용자 보고 두 가지 — v3_wild3_calm_mirror.yaml
# 머리 주석). 다음 학습부터 학습 세계와 게임 세계(eco.IntegratedV3.GrazeCalm·RestKeep 1)를 같게 하려는 판이다 — 이 판으로 아직 학습하지 않았다.
# 자동 생성 — results/v3/calm/make_calm_configs.py (손으로 고치지 않는다. v3_r7_train.yaml 이 바뀌면 다시 만든다).
# = configs/v3_r7_train.yaml(아래 그대로) + 바꾼 곳 셋: version 3.r7calm, features.repertoire.graze_*, features.wild_flight.rest_keep*.
#   train.repertoire f_dec·ent_coef_base 는 R7 값 그대로다 — 이 세계로 학습하기 전에 `python train_v3.py measure-fdec --config configs/v3_r7_calm_train.yaml`
#   로 다시 잰다(거리 두기는 덮기가 아니라 결정 줄은 그대로지만 궤적이 달라진다).
#
# ── 아래는 v3_r7_train.yaml 그대로 (version 과 두 블록의 새 칸만 다르다) ──
"""

SETS = (
    ("v3_wild3_calm_mirror.yaml", "v3_wild3_mirror.yaml", HEAD_MIRROR, 'version: "3.wild3"\n', 'version: "3.wild3calm"\n'),
    ("v3_wild3_route5_calm_mirror.yaml", "v3_wild3_route5_mirror.yaml", HEAD_ROUTE5, 'version: "3.wild3route5"\n', 'version: "3.wild3route5calm"\n'),
    ("v3_r7_calm_train.yaml", "v3_r7_train.yaml", HEAD_TRAIN, 'version: "3.r7"\n', 'version: "3.r7calm"\n'),
)


def _one(text: str, old: str, new: str, what: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{what}: {old.strip()!r} 가 한 번 나오지 않는다 ({text.count(old)} 번)")
    return text.replace(old, new)


def build(src_name: str, head: str, ver_old: str, ver_new: str) -> str:
    text = (CONFIGS / src_name).read_text(encoding="utf-8")
    text = _one(text, ver_old, ver_new, src_name)
    text = _one(text, GRAZE_ANCHOR, GRAZE_ANCHOR + GRAZE_LINES, src_name)
    text = _one(text, REST_ANCHOR, REST_ANCHOR + REST_LINES, src_name)
    return head + text


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="쓰지 않고 올려 둔 파일과 같은지만 본다")
    a = ap.parse_args(argv)
    bad = []
    for out_name, src_name, head, vo, vn in SETS:
        text = build(src_name, head, vo, vn)
        out = CONFIGS / out_name
        if a.check:
            if not out.exists() or out.read_text(encoding="utf-8") != text:
                bad.append(out_name)
            continue
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"썼다: {out}")
    if bad:
        print(f"다르다: {bad}")
        sys.exit(1)
    if a.check:
        print("같다")


if __name__ == "__main__":
    main()
