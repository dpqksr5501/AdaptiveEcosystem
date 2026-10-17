#!/bin/sh
# 야생 3단계 지역 날씨 측정 묶음 (10-18, herbivore_rl/ 에서 sh results/v3/wild3/run_all.sh). 결과 results/v3/wild3/runs/ (커밋하지 않는다),
# 표 results/v3/wild3/summarize_weather.py → results/v3/wild3/summary.md·summary.json. 두뇌 = 지금 게임 두뇌 R1b-F(run_mirror.py 기본, 마스크 argmax).
# 세계 = 언리얼과 같은 지도 짝(지도 (세션, 지역) 마다 그 지역 먹이 지도·나무 원판·날씨). 기준 = 나무 거울(날씨 없음), 같은 시드·같은 지도 짝.
set -e
R="python results/v3/mirror/run_mirror.py --diag --out-dir results/v3/wild3/runs --deer 128"
T=configs/v3_wild2_trees_mirror.yaml
W=configs/v3_wild3_mirror.yaml
L=results/v3/wild2/trees/tree_layout.json
python results/v3/wild3/make_wild3_config.py --check
# 240초: 지도 9장(세션 20000~20002 × 지역 3) × 반복 10 = 90 세계(지역마다 30), 시드 32000~32089
P240="--unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089 --unreal-obstacles $L"
$R $P240 --config $T --name trees_240
$R $P240 --config $W --name wild3_240
# 민감도(같은 세계): 관측 visibility 에 날씨를 싣지 않음 · 고지 눈 세기 0.5(사슴 × 0.8, 늑대 × 0.925, 시야 × 0.85)
$R $P240 --config $W --set wild_weather.obs_visibility=false --name wild3_novis_240
$R $P240 --config $W --set 'wild_weather.regions={"Barren":["clear",0.0],"Forest":["rain",1.0],"Highland":["snow",0.5]}' --name wild3_snow05_240
# 고지 눈 나눠 보기: 이동 배수만(시야 1) · 시야 배수만(이동 1)
$R $P240 --config $W --set wild_weather.snow_sight=1.0 --name wild3_snowspeed_240
$R $P240 --config $W --set wild_weather.snow_deer_speed=1.0 --set wild_weather.snow_wolf_speed=1.0 --name wild3_snowsight_240
# 16분(게임 8일): 지도 30장(세션 20000~20009 × 지역 3) × 반복 1 = 30 세계(지역마다 10), 시드 32000~32029
P16="--unreal-maps 20000-20009 --replicates 1 --seeds 32000-32029 --unreal-obstacles $L --steps 7200"
$R $P16 --config $T --name trees_16m
$R $P16 --config $W --name wild3_16m
# 끼임: 짝 지도 90 세계 × 240초(지도 지역마다 나무·날씨) · 눈 + 숲 원판 24 그루 30 세계 × 16 분(고지 눈 배수로 느려진 사슴·늑대가 줄기에 끼지 않나)
python results/v3/wild2/stuck_check.py --config $W --seeds 32000-32089 --steps 1800 --unreal-maps 20000-20002 --replicates 10 --unreal-obstacles $L --out results/v3/wild3/runs/stuck_wild3_pair.json
python results/v3/wild2/stuck_check.py --config $W --set wild_weather.region=Highland --seeds 32000-32029 --steps 7200 --out results/v3/wild3/runs/stuck_snow_long.json
python results/v3/wild3/summarize_weather.py
