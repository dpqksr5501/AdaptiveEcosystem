#!/usr/bin/env bash
# 나무 자리 정밀 탐색 사슬 (10-27). herbivore_rl/ 에서 돈다. 워커 6, 한 번에 하나씩. 시드 34900~34999 만 (sense·place 가 그 밖을 거부).
#   OUT = 원자료 폴더 (저장소 밖), L = 기록 폴더.   bash run_all.sh <단계 A|B|C> <OUT> <L>
set -u
cd "$(dirname "$0")/../../../.."            # herbivore_rl/
export PYTHONUTF8=1
ST=$1; OUT=$2; L=$3
S=results/v3/level_sense/sense.py
P=results/v3/level_sense/placement/place.py
mkdir -p "$L"
log() { echo "$1 $(date +%T)" >> "$L/chain.status"; }
if [ "$ST" = A ]; then   # 1. 바탕 공간 지도 (파이썬 실행기, 지역 하나씩) — I Barren 은 하네스 첫 측정 것을 그대로 쓴다
  for BR in "I Forest" "J Barren" "J Forest"; do set -- $BR
    python $S run --base $1 --out "$OUT" --variants base --runner python --maps --regions $2 --workers 6 > "$L/A_maps_$1_$2.log" 2>&1; log "A maps $1 $2 $?"
  done
fi
if [ "$ST" = B ]; then   # 2. 격자 훑기 (20 m, 작은 숲 8 그루·반지름 10 m) 3. 자리 띠 20 그루 × 씨 2 4. 무작위 같은 수 5. 다시 재기 바탕
  for BR in "I Barren" "I Forest" "J Barren" "J Forest"; do set -- $BR
    python $S scan --base $1 --region $2 --out "$OUT" --grid 20 --workers 6 --tag grid20 --metrics tree > "$L/B_grid_$1_$2.log" 2>&1; log "B grid $1 $2 $?"
    Z=""; for z in d0-5 d5-10 d10-20 d20-40 flee_hi flee_lo spotd_hi spotw_hi rest_hi graze_hi edge; do Z="$Z zone_${z}_n20_s1 zone_${z}_n20_s2"; done
    python $P run --out "$OUT" --base $1 --region $2 --variants base $Z trees:8:rand:1 trees:8:rand:2 trees:20:rand:1 trees:20:rand:2 trees:40:rand:1 trees:40:rand:2 \
      > "$L/B_zones_$1_$2.log" 2>&1; log "B zones $1 $2 $?"
    python $P run --out "$OUT" --base $1 --region $2 --world G --variants base > "$L/B_base_G_$1_$2.log" 2>&1; log "B base r7e G $1 $2 $?"
    python $P run --out "$OUT" --base $1 --region $2 --brain r1bf --variants base > "$L/B_base_r1bfN_$1_$2.log" 2>&1; log "B base r1bf N $1 $2 $?"
    python $P run --out "$OUT" --base $1 --region $2 --brain r1bf --world G --variants base > "$L/B_base_r1bfG_$1_$2.log" 2>&1; log "B base r1bf G $1 $2 $?"
  done
fi
if [ "$ST" = C ]; then   # 6. 단계 B 분석으로 고른 변형 — placement/stage_c.txt 한 줄 = '<바탕> <지역> <두뇌> <세계> <변형…>'
  while read -r B R BR W V; do [ -z "$B" ] && continue; case "$B" in \#*) continue;; esac
    python $P run --out "$OUT" --base $B --region $R --brain $BR --world $W --variants base $V < /dev/null > "$L/C_${B}_${R}_${BR}_${W}.log" 2>&1; log "C $B $R $BR $W $?"
  done < results/v3/level_sense/placement/stage_c.txt
fi
python $P analyze --out "$OUT" > "$L/analyze_$ST.log" 2>&1; log "analyze $ST $?"
log "done $ST"
