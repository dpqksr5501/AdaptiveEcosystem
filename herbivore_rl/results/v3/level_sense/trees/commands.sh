#!/bin/bash
# 나무 쪽 측정 (10-27) — 실제로 돌린 명령 그대로 (O 만 바꿔 쓴다). herbivore_rl/ 에서 Git Bash 로.
# 평가기 판 160 개(약 82 분) → 파이썬 길 떼어 보기 16 개(+60 무작위, 약 6 분씩) → 문 앞 고리 길 떼어 보기 5 개. 워커 5 (다른 측정과 CPU 를 나눔).
# 원자료(기록 json.gz)는 저장소 밖 O 에 두고 지문만 raw_fingerprints.json 에 남겼다.
cd "$(dirname "$0")/../../../.."   # herbivore_rl/
export PYTHONUTF8=1
S=results/v3/level_sense/sense.py
O=${O:-../AdaptiveEcosystem/Saved/LevelSense/trees}
W=5
run() { echo "### $(date +%T) $*"; python $S run --out $O --workers $W "$@" 2>&1 | grep -E "^\[|^바탕|Error|Traceback|SystemExit|못" ; echo "### rc=${PIPESTATUS[0]} $(date +%T)"; }

# 1·2. 수·자리 (평가기, 두뇌 2 × 바탕 2 × 세계 2 × 지역 2, 나무를 더한 지역 세계만)
# I 바탕 Forest 는 graze 10 그루·path 17 그루밖에 안 들어가(sense.py list 로 확인 — 그 뒤 그루는 4000 번 안에 자리를 못 찾음) 같은 수 무작위를 따로 돌린다.
for world in N G; do for region in Barren Forest; do for base in I J; do for brain in r7e r1bf; do
  if [ "$base$region" = "IForest" ]; then extra="trees:10:graze trees:17:path trees:17:rand"; else extra="graze30 path30"; fi
  run --base $base --brain $brain --world $world --region $region --regions $region --variants base t10 t30 t60 t120 ring30 clump30 edge30 $extra
done; done; done; done

# 3. 길 떼어 보기 (+60 무작위, 파이썬 실행기만 — 하네스가 env_v2.world 원판 함수를 감싼 세계, 게임에 없는 세계)
P="gate trees:60:rand+gate+paths:sight trees:60:rand+gate+paths:move trees:60:rand+gate+paths:obs"
for world in N G; do for brain in r7e r1bf; do
  run --base I --brain $brain --world $world --region Barren --regions Barren --runner python --variants $P
done; done

# 3-2. 문 앞 고리 30 그루 길 떼어 보기 (2 의 고리 효과가 어느 길인지 — 추가, N 만. R1b-F 는 나무 관측 칸이 없어 obs 를 뺐다)
run --base I --brain r7e --world N --region Barren --regions Barren --runner python --variants trees:30:ring+gate+paths:move trees:30:ring+gate+paths:sight trees:30:ring+gate+paths:obs
run --base I --brain r1bf --world N --region Barren --regions Barren --runner python --variants trees:30:ring+gate+paths:move trees:30:ring+gate+paths:sight

# 표·json
python results/v3/level_sense/trees/analyze.py --out $O --save
