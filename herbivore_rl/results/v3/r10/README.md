# R10 — 16 종 범용 동물 두뇌 (파이썬 학습·평가 줄기)

설계 `AdaptiveEcosystem/Docs/RL_Policy/RL_R10_UNIVERSAL_FAUNA_DESIGN.md`(사용자 답 16 절) · 0 단계 사양 `RL_R10_PHASE0_SPEC.md`.
R9(`env_v2/r9_*`, `results/v3/r9/`)는 그대로 두고 새 꾸러미 `herbivore_rl/r10/` 에 짰다.

## 무엇이 다른가 (R9 → R10)

| | R9 | R10 |
|---|---|---|
| 세계 | 평평한 2D 정사각형 | 높이·물·가림·먹이 층이 있는 무작위 지형(`r10/mapgen.py`), 땅·물·하늘 몸 물리 |
| 종 | 6 종 한도, 코드에 종 이름 | 종 카드 16 개(`herbivore_rl/species/*.json`), 코드에 종 이름 없음 |
| 누가 누구를 무나 | 종 표 | 몸무게 비율 하나(`combat.kill_mass_ratio`) + 같은 매체 + 머리 앞·다가감 |
| 감각 | 115 칸 | 206 칸(자기 14·몸 17·8 방향 × 6·발밑 6·다른 동물 8 × 12·같은 종 4·환경 6·예비 15) |
| 행동 | 19 칸 | 24 칸(오르기·내리기·급강하 + 예비 2), 몸이 못 하는 칸은 감각의 몸 벡터로 막음 |
| 몸 숫자가 바뀌면 | 몸 해시 거부 → rebody | 몸 벡터가 감각에 있고 학습 때 ±15% 흔듦 → 범위 안이면 그대로 |

## 파일

| 파일 | 내용 |
|---|---|
| `r10/contract.py` | 감각 S1·행동 A1 이름·정규화·마스크·계약 해시 |
| `r10/terrain.py` · `r10/mapgen.py` | 층 지형·맵 카드(npz) · 맵 무작위 생성기(시드: 학습 50000~59999, 점검 60000~60999, 시험 61000~61999 잠금) |
| `r10/species.py` | 종 카드 검사·몸 벡터·흔들기·이름 모를 동물 카드 |
| `r10/world.py` · `r10/senses.py` | 세계 한 걸음(이동·물기·먹기·대사·번식·사체) · 감각 206 칸 |
| `r10/policy.py` · `r10/rule_brain.py` | 감각 마스크 정책(SB3·numpy) · 공통 규칙 두뇌(잣대·0 바퀴 상대) |
| `r10/vec_env.py` | 한 종 학습 칸 (SB3 VecEnv) |
| `make_cards.py` · `card_sources/` | 언리얼 값 초안(칸마다 출처) → 종 카드. 언리얼 값이 바뀌면 다시 돌림 |
| `train_r10.py` · `eval_r10.py` | 한 종 학습 · 처음 보는 맵에서 배운 두뇌 대 규칙 두뇌 |
| `tests/test_r10_base.py` · `tests/test_r10_world.py` | 계약·생성기·카드·물리·감각 회전 불변·종 수 불변·결정성 (23 개) |

## 명령 (herbivore_rl/ 에서, PYTHONUTF8=1)

```
python -m pytest -p no:cacheprovider -q tests/test_r10_base.py tests/test_r10_world.py
python -X utf8 results/v3/r10/make_cards.py                                     # 종 카드 다시 만들기
python -X utf8 results/v3/r10/eval_r10.py --only deer wolf boar --flat           # 모두 규칙 두뇌 (잣대)
python -X utf8 results/v3/r10/train_r10.py --species deer --only deer wolf boar --flat --decisions 5000000 --out ckpt/r10/small
python -X utf8 results/v3/r10/eval_r10.py --only deer wolf boar --flat --brain deer=ckpt/r10/small/deer_<결정>.npz
```

## 지금 알려진 것 (2026-11-19)

- **먹이·기운 숫자는 아직 맞추지 않았다.** 크기 법칙 어림이다. 16 종 규칙 두뇌 시험에서 물고기가 수위가 내려가면 물 밖에 갇히고(물에서 죽음), 검독수리는 규칙 두뇌로 사냥을 못 해 굶는다. R9 C0 관문처럼 학습 앞 관문에서 맞춘다.
- **언리얼 값으로는 사슴(9 m/s)이 늑대(7.2 m/s)보다 빠르다.** 열린 들판 추격으로는 거의 못 잡는다. 늑대가 매복·기습을 배워야 하는 세계다. Native 늑대의 덮치기 속도(`card_sources/wolf.json` pounce)는 아직 몸에 넣지 않았다.
- **언리얼 RuleFauna 는 종 이름 목록으로 사냥한다.** Native 사슴은 규칙 포식자가 못 잡는 식의 제약도 있다. R10 은 몸무게 비율로 정하므로, 언리얼에 넣을 때 실행기 쪽 규칙을 맞춰야 한다(12 절, 조연우 님과 범위 정하기).
- 환경 감각의 '큰 소리 방향'은 파이썬 세계에 플레이어가 없어 늘 0 이다.
- 마스크 정책은 sb3-contrib 없이 직접 짰다(이 PC 에 설치가 막힘). 감각의 몸 벡터(b_swim·b_fly)로 막을 칸을 계산한다.
