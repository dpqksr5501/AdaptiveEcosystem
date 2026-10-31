#!/bin/sh
# 야생 1단계 측정 묶음 (herbivore_rl/ 에서 sh results/v3/wild1/run_all.sh). 결과 results/v3/wild1/runs/ (커밋하지 않는다), 표 summarize.py
set -e
R="python results/v3/mirror/run_mirror.py --diag --out-dir results/v3/wild1/runs"
W=configs/v3_wild1_mirror.yaml
for D in 128 64; do
  if [ $D = 128 ]; then S=32000-32089; L=32000-32029; else S=33000-33089; L=33000-33029; fi
  $R --deer $D --seeds $S --name d${D}_base
  $R --deer $D --seeds $S --config $W --name d${D}_wild1
  $R --deer $D --seeds $S --config $W --disable wild_reserve --name d${D}_wild1_no_reserve
  $R --deer $D --seeds $S --config $W --disable wild_satiation --name d${D}_wild1_no_satiation
  $R --deer $D --seeds $S --config $W --disable realism_vision,realism_hearing --name d${D}_wild1_no_detect
  $R --deer $D --seeds $S --config $W --disable wild_flight --name d${D}_wild1_no_flight
  $R --deer $D --seeds $L --steps 7200 --name d${D}_base_long
  $R --deer $D --seeds $L --steps 7200 --config $W --name d${D}_wild1_long
done
