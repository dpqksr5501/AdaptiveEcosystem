#!/bin/sh
# 야생 2단계 1 (은신처 먹이 부족) 측정 묶음 (herbivore_rl/ 에서 sh results/v3/wild2/run_all.sh). 결과 results/v3/wild2/runs/ (커밋하지 않는다),
# 표 results/v3/wild2/summarize.py. wild1 = 1단계 + 10-16 고침 + 10-17 늑대 몸 여유(지금까지의 기준), wild2 = 그 위에 은신처 먹이 부족
set -e
R="python results/v3/mirror/run_mirror.py --diag --out-dir results/v3/wild2/runs"
W1=configs/v3_wild1_mirror.yaml
W2=configs/v3_wild2_mirror.yaml
for N in wild1 wild2; do
  if [ $N = wild1 ]; then C=$W1; else C=$W2; fi
  $R --deer 128 --seeds 32000-32089 --config $C --name d128_$N
  $R --deer 128 --seeds 32000-32029 --steps 7200 --config $C --name d128_${N}_long
  $R --deer 128 --unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089 --config $C --name pair_d128_${N}_u20000-20002_k10
done
