#!/bin/sh
# 야생 2단계 측정 묶음 (1 은신처 먹이 부족 · 2 늑대 무리 · 3 세로 장애물 · 10-17 고침 · 10-17 장애물 돌아가기) (herbivore_rl/ 에서 sh results/v3/wild2/run_all.sh). 결과 results/v3/wild2/runs/ (커밋하지 않는다),
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
# 야생 2단계 2 늑대 무리·협동 사냥 (10-17): pack = 늑대 4 + wild_pack, w4 = 늑대 4 만(wild_pack 끔).
# 10-17 고침: 이 판들은 은신처 먹이 부족을 끈 판이다(처음 설정이 사용자 말을 잘못 읽어 뺐다). 설정에 다시 넣었으므로 --disable realism_cover_food 로 다시 만든다
P=configs/v3_wild2_pack_mirror.yaml
F=realism_cover_food
$R --deer 128 --seeds 32000-32089 --config $P --disable $F --name d128_pack
$R --deer 128 --seeds 32000-32089 --config $P --disable wild_pack,$F --name d128_w4
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $P --disable $F --name d128_pack_long
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $P --disable wild_pack,$F --name d128_w4_long
$R --deer 128 --unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089 --config $P --disable $F --name pair_d128_pack_u20000-20002_k10
# 야생 2단계 3 세로 장애물 (10-17): 숲 배치(줄기 1 ha 250·바위 5). 짝 비교는 언리얼과 같은 원판(make_obstacle_maps.py → obstacle_maps/)
# (10-17 고침 전 판 — 은신처 먹이 부족 끔. 10-17 돌아가기를 넣은 뒤에는 --set obstacles.detour=false 로 그때와 비트 동일)
O=configs/v3_wild2_obstacle_mirror.yaml
python results/v3/wild2/make_obstacle_maps.py --sessions 20000-20002
$R --deer 128 --seeds 32000-32089 --config $O --set obstacles.detour=false --disable $F --name d128_obst
$R --deer 128 --unreal-maps 20000-20002 --unreal-obstacles results/v3/wild2/obstacle_maps --replicates 10 --seeds 32000-32089 --config $O --set obstacles.detour=false --disable $F --name pair_d128_obst_u20000-20002_k10
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $O --set obstacles.detour=false --disable $F --name d128_obst_long
# 10-17 고침: 지금 기본값(늑대 4 + 협동 + 몸 여유 1 m + 은신처 먹이 부족, 장애물은 언리얼 레벨에 원판이 없어 pack 판이 언리얼 기본의 거울)
$R --deer 128 --seeds 32000-32089 --config $P --name d128_packfood
$R --deer 128 --unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089 --config $P --name pair_d128_packfood_u20000-20002_k10
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $P --name d128_packfood_long
$R --deer 128 --seeds 32000-32089 --config $O --set obstacles.detour=false --name d128_obstfood
$R --deer 128 --unreal-maps 20000-20002 --unreal-obstacles results/v3/wild2/obstacle_maps --replicates 10 --seeds 32000-32089 --config $O --set obstacles.detour=false --name pair_d128_obstfood_u20000-20002_k10
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $O --set obstacles.detour=false --name d128_obstfood_long
# 10-17 장애물 끼임 고침(돌아가기, obstacles.detour 켬 — 지금 장애물 거울). 위 obstfood 판 = 돌아가기를 넣기 전 코드(끈 판과 비트 동일)
$R --deer 128 --seeds 32000-32089 --config $O --name d128_obstdet
$R --deer 128 --seeds 32000-32029 --steps 7200 --config $O --name d128_obstdet_long
$R --deer 128 --unreal-maps 20000-20002 --unreal-obstacles results/v3/wild2/obstacle_maps --replicates 10 --seeds 32000-32089 --config $O --name pair_d128_obstdet_u20000-20002_k10
# 끼임 세기(30 세계 × 16 분): 켬 · 끔 · 원판 없는 무리 거울(은신처 둘레 기어감의 기준)
python results/v3/wild2/stuck_check.py --seeds 32000-32029 --steps 7200 --out results/v3/wild2/runs/stuck_obstdet.json
python results/v3/wild2/stuck_check.py --seeds 32000-32029 --steps 7200 --set obstacles.detour=false --out results/v3/wild2/runs/stuck_obstfood.json
python results/v3/wild2/stuck_check.py --config $P --seeds 32000-32029 --steps 7200 --out results/v3/wild2/runs/stuck_packfood.json
