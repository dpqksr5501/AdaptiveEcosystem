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
# 야생 2단계 2 늑대 무리·협동 사냥 (10-17): pack = 늑대 4 + wild_pack, w4 = 늑대 4 만(wild_pack 끔). 은신처 먹이 부족은 끈다(사용자 결정 10-17)
P=configs/v3_wild2_pack_mirror.yaml
$R --deer 128 --seeds 32000-32089 --config $P --name d128_pack
$R --deer 128 --seeds 32000-32089 --config $P --disable wild_pack --name d128_w4
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $P --name d128_pack_long
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $P --disable wild_pack --name d128_w4_long
$R --deer 128 --unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089 --config $P --name pair_d128_pack_u20000-20002_k10
# 야생 2단계 3 세로 장애물 (10-17): 숲 배치(줄기 1 ha 250·바위 5). 짝 비교는 언리얼과 같은 원판(make_obstacle_maps.py → obstacle_maps/)
O=configs/v3_wild2_obstacle_mirror.yaml
python results/v3/wild2/make_obstacle_maps.py --sessions 20000-20002
$R --deer 128 --seeds 32000-32089 --config $O --name d128_obst
$R --deer 128 --unreal-maps 20000-20002 --unreal-obstacles results/v3/wild2/obstacle_maps --replicates 10 --seeds 32000-32089 --config $O --name pair_d128_obst_u20000-20002_k10
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $O --name d128_obst_long
