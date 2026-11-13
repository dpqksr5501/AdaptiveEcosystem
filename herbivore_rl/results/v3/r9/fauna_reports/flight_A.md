1 단계 평지 — 물소 물가는 2 단계, 첫 밤 결과는 정식 판정이 아님

- 만든 때 2026-11-13 07:39:12 · 설정 `configs/v3_r9_fauna.yaml` · 두뇌 {"deer": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\start\\deer_v0.npz", "wolf": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\flight\\A\\wolf_r0_10006528.npz", "boar": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\start\\boar_v0.npz", "buffalo": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\flight\\A\\buffalo_r0_10027008.npz", "leopard": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\flight\\A\\leopard_r0_5013504.npz", "fox": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\flight\\A\\fox_r0_5013504.npz"}
- 보고만 한다(판정 아님). 칸마다 사건 30 개 넘을 때만 비율을 적는다. 정의는 JSON 'defs'.

## 두뇌 판: learned
- deer mlp:deer_v0.npz · wolf mlp:wolf_r0_10006528.npz · boar mlp:boar_v0.npz · buffalo mlp:buffalo_r0_10027008.npz · leopard mlp:leopard_r0_5013504.npz · fox mlp:fox_r0_5013504.npz

### S1 늑대 무리 대 물소 (어른 3 + 송아지 1)

| 늑대 | 어른 죽임 몫 | 송아지 죽임 몫 | 늑대 죽음 몫 | 늑대 HP 잃음/마리 | 받기 | 반격 | 앞자리 몫 |
|---|---|---|---|---|---|---|---|
| 1 | 0.000 | 0.000 | 0.000 | 0.028 | 0 | 2 | 0.104 |
| 2 | 0.000 | 0.000 | 0.013 | 0.035 | 1 | 4 | 0.440 |
| 3 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0.818 |
| 4 | 0.000 | 0.000 | 0.000 | 0.004 | 0 | 1 | 0.329 |
| 6 | 0.008 | 0.025 | 0.000 | 0.006 | 1 | 2 | 0.371 |
- 현실 기준(MacNulty 2014): 혼자 0.01, 마리당 오즈 × 1.4. 기대: 1~2 마리는 낮고 늑대가 다침, 3~4 마리부터 오름. 이상 신호: 어른 1 마리 성공 ≥ 0.2.

### S2 늑대 1 ↔ 표범 1

- 세계 40 · 늑대 죽음 0 · 표범 죽음 0 · 둘 다 0 · 아무도 40 · 늑대→표범 물림 0 · 표범→늑대 물림 0
- 기대: 대개 다치고 떨어짐. 이상 신호: '둘 다 죽음' 잦음.

### 자연 세계 N (base) — 20 세계 × 1350 결정 (87.3 초)

- 죽음(종: 물림·반격·굶음): deer 101·1·147 · wolf 6·1·1 · boar 8·0·48 · buffalo 0·0·16 · leopard 2·0·2 · fox 8·0·27
- T-A 덤빔 11 (끝나지 않음 2):
  - pack1|adult|deer_gt4: 덤빔 3 · 성공 0 (몫 —) · 늑대 HP 잃음 0.58 · 늑대 죽음 0 · 시작 E 0.22 · 10 단위 안 사슴 1.7
  - pack1|calf|deer_gt4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.00 · 늑대 죽음 0 · 시작 E 0.17 · 10 단위 안 사슴 1.0
  - pack2|adult|deer_gt4: 덤빔 3 · 성공 0 (몫 —) · 늑대 HP 잃음 0.14 · 늑대 죽음 0 · 시작 E 0.50 · 10 단위 안 사슴 3.3
  - pack3|adult|deer_gt4: 덤빔 2 · 성공 0 (몫 —) · 늑대 HP 잃음 0.00 · 늑대 죽음 0 · 시작 E 0.62 · 10 단위 안 사슴 5.5
  - pack5+|adult|deer_gt4: 덤빔 2 · 성공 0 (몫 —) · 늑대 HP 잃음 0.14 · 늑대 죽음 0 · 시작 E 0.71 · 10 단위 안 사슴 0.0
- T-C 위협 결정 822: 마주 봄 0.418 · 도망 0.006 · 받기 0.000 · 동족 거리 위협 37.29 / 평소 33.01
- T-D 표범 먹잇감 (죽임/만남/D): boar 0/12041/-1.00 · buffalo 0/6845/-1.00 · deer 10/32818/0.05 · fox 2/5134/0.16 · wolf 6/4858/0.71
  - 무게 띠: 20-80kg 15/43517/0.35 · <20kg 3/6090/0.29 · >80kg 0/12089/-1.00
- T-H 죽임 표: buffalo>deer:gore 1 · buffalo>wolf:counter 1 · leopard>deer:bite 10 · leopard>fox:bite 2 · leopard>wolf:bite 6 · wolf>boar:bite 8 · wolf>deer:bite 91 · wolf>fox:bite 6 · wolf>leopard:bite 2
  - 표범 죽음 원인 {'bite': 2, 'starve': 2} · 은신처 안 물림 {'leopard>deer': 1} · 물소 받기 HP/물소-일 {"deer": 0.0108, "wolf": 0.0016, "boar": 0.0, "leopard": 0.0, "fox": 0.0}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 102329 중 칸에 없던 몫 0.0073 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 24.4 · 5 단위 안 몫 0.029 · 함께 덤빔 몫 0.000 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 19.4 · 5 단위 안 몫 0.232 · 함께 덤빔 몫 0.009 (현실은 혼자 — 보고만)

### 자연 세계 N (buffalo_land) — 20 세계 × 1350 결정 (55.3 초)

- 죽음(종: 물림·반격·굶음): deer 6·0·5 · wolf 0·1·36 · boar 7·0·65 · buffalo 1·0·26 · leopard 1·0·3 · fox 9·0·27
- T-A 덤빔 14 (끝나지 않음 1):
  - pack1|adult|deer_le4: 덤빔 6 · 성공 0 (몫 —) · 늑대 HP 잃음 0.37 · 늑대 죽음 1 · 시작 E 0.18 · 10 단위 안 사슴 0.7
  - pack2|adult|deer_le4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.47 · 늑대 죽음 0 · 시작 E 0.25 · 10 단위 안 사슴 0.0
  - pack3|adult|deer_le4: 덤빔 5 · 성공 0 (몫 —) · 늑대 HP 잃음 0.73 · 늑대 죽음 0 · 시작 E 0.58 · 10 단위 안 사슴 0.6
  - pack5+|adult|deer_le4: 덤빔 2 · 성공 1 (몫 —) · 늑대 HP 잃음 1.72 · 늑대 죽음 1 · 시작 E 0.33 · 10 단위 안 사슴 0.0
- T-C 위협 결정 1396: 마주 봄 0.236 · 도망 0.012 · 받기 0.001 · 동족 거리 위협 30.34 / 평소 33.16
- T-D 표범 먹잇감 (죽임/만남/D): boar 0/16869/-1.00 · buffalo 0/12916/-1.00 · deer 1/2180/1.00 · fox 0/8614/-1.00 · wolf 0/2505/-1.00
  - 무게 띠: 20-80kg 1/13390/1.00 · <20kg 0/8677/-1.00 · >80kg 0/21017/-1.00
- T-H 죽임 표: buffalo>wolf:counter 1 · leopard>deer:bite 1 · wolf>boar:bite 7 · wolf>buffalo:bite 1 · wolf>deer:bite 5 · wolf>fox:bite 9 · wolf>leopard:bite 1
  - 표범 죽음 원인 {'bite': 1, 'starve': 3} · 은신처 안 물림 {} · 물소 받기 HP/물소-일 {"deer": 0.0069, "wolf": 0.0025, "boar": 0.0006, "leopard": 0.0, "fox": 0.0}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 5166 중 칸에 없던 몫 0.0490 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 28.4 · 5 단위 안 몫 0.013 · 함께 덤빔 몫 0.000 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 11.9 · 5 단위 안 몫 0.212 · 함께 덤빔 몫 0.030 (현실은 혼자 — 보고만)

## 두뇌 판: rules
- deer rule:RULE_DEER · wolf rule:RULE_WOLF · boar rule:RULE_BOAR · buffalo rule:RULE_BUFFALO · leopard rule:RULE_LEOPARD · fox rule:RULE_FOX

### S1 늑대 무리 대 물소 (어른 3 + 송아지 1)

| 늑대 | 어른 죽임 몫 | 송아지 죽임 몫 | 늑대 죽음 몫 | 늑대 HP 잃음/마리 | 받기 | 반격 | 앞자리 몫 |
|---|---|---|---|---|---|---|---|
| 1 | 0.000 | 0.000 | 1.000 | 1.157 | 122 | 36 | 0.756 |
| 2 | 0.025 | 0.075 | 0.963 | 1.136 | 249 | 83 | 0.727 |
| 3 | 0.033 | 0.100 | 0.967 | 1.141 | 373 | 146 | 0.729 |
| 4 | 0.092 | 0.150 | 0.925 | 1.168 | 363 | 241 | 0.709 |
| 6 | 0.300 | 0.450 | 0.825 | 1.118 | 449 | 379 | 0.682 |
- 현실 기준(MacNulty 2014): 혼자 0.01, 마리당 오즈 × 1.4. 기대: 1~2 마리는 낮고 늑대가 다침, 3~4 마리부터 오름. 이상 신호: 어른 1 마리 성공 ≥ 0.2.

### S2 늑대 1 ↔ 표범 1

- 세계 40 · 늑대 죽음 16 · 표범 죽음 24 · 둘 다 0 · 아무도 0 · 늑대→표범 물림 73 · 표범→늑대 물림 54
- 기대: 대개 다치고 떨어짐. 이상 신호: '둘 다 죽음' 잦음.

### 자연 세계 N (base) — 20 세계 × 1350 결정 (132.4 초)

- 죽음(종: 물림·반격·굶음): deer 119·143·213 · wolf 9·3·0 · boar 20·0·16 · buffalo 2·0·19 · leopard 3·0·0 · fox 14·19·2
- T-A 덤빔 12 (끝나지 않음 6):
  - pack1|adult|deer_gt4: 덤빔 6 · 성공 0 (몫 —) · 늑대 HP 잃음 1.05 · 늑대 죽음 1 · 시작 E 0.86 · 10 단위 안 사슴 6.0
  - pack1|calf|deer_gt4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.10 · 늑대 죽음 0 · 시작 E 0.97 · 10 단위 안 사슴 2.0
  - pack2|adult|deer_gt4: 덤빔 4 · 성공 1 (몫 —) · 늑대 HP 잃음 0.41 · 늑대 죽음 0 · 시작 E 0.63 · 10 단위 안 사슴 3.2
  - pack3|adult|deer_gt4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.00 · 늑대 죽음 0 · 시작 E 0.96 · 10 단위 안 사슴 5.0
- T-C 위협 결정 770: 마주 봄 0.374 · 도망 0.005 · 받기 0.034 · 동족 거리 위협 20.85 / 평소 27.80
- T-D 표범 먹잇감 (죽임/만남/D): boar 7/30223/-0.17 · buffalo 0/14089/-1.00 · deer 43/127169/0.11 · fox 7/8387/0.48 · wolf 9/32183/-0.06
  - 무게 띠: 20-80kg 57/173817/0.16 · <20kg 8/13039/0.36 · >80kg 1/25195/-0.80
- T-H 죽임 표: boar>fox:counter 8 · boar>wolf:counter 1 · buffalo>deer:gore 143 · buffalo>fox:counter 2 · buffalo>fox:gore 9 · buffalo>wolf:counter 1 · buffalo>wolf:gore 1 · fox>deer:bite 1 · leopard>boar:bite 7 · leopard>deer:bite 43 · leopard>fox:bite 7 · leopard>wolf:bite 9 · wolf>boar:bite 13 · wolf>buffalo:bite 2 · wolf>deer:bite 75 · wolf>fox:bite 7 · wolf>leopard:bite 3
  - 표범 죽음 원인 {'bite': 3} · 은신처 안 물림 {'leopard>deer': 15, 'leopard>boar': 3, 'leopard>fox': 5, 'fox>deer': 11, 'fox>leopard': 5} · 물소 받기 HP/물소-일 {"deer": 1.5604, "wolf": 0.0322, "boar": 0.0092, "leopard": 0.004, "fox": 0.0846}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 242296 중 칸에 없던 몫 0.0900 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 13.8 · 5 단위 안 몫 0.386 · 함께 덤빔 몫 0.021 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 2.1 · 5 단위 안 몫 0.567 · 함께 덤빔 몫 0.143 (현실은 혼자 — 보고만)

### 자연 세계 N (buffalo_land) — 20 세계 × 1350 결정 (95.6 초)

- 죽음(종: 물림·반격·굶음): deer 22·22·4 · wolf 17·66·0 · boar 56·1·23 · buffalo 11·0·23 · leopard 9·3·0 · fox 43·33·0
- T-A 덤빔 61 (끝나지 않음 6):
  - pack1|adult|deer_le4: 덤빔 28 · 성공 5 (몫 —) · 늑대 HP 잃음 5.28 · 늑대 죽음 13 · 시작 E 0.56 · 10 단위 안 사슴 0.4
  - pack2|adult|deer_le4: 덤빔 19 · 성공 2 (몫 —) · 늑대 HP 잃음 18.25 · 늑대 죽음 25 · 시작 E 0.51 · 10 단위 안 사슴 0.4
  - pack2|calf|deer_le4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.83 · 늑대 죽음 0 · 시작 E 0.85 · 10 단위 안 사슴 0.0
  - pack3|adult|deer_le4: 덤빔 7 · 성공 3 (몫 —) · 늑대 HP 잃음 5.13 · 늑대 죽음 8 · 시작 E 0.84 · 10 단위 안 사슴 0.0
  - pack4|adult|deer_le4: 덤빔 5 · 성공 1 (몫 —) · 늑대 HP 잃음 6.45 · 늑대 죽음 8 · 시작 E 0.81 · 10 단위 안 사슴 0.0
  - pack5+|adult|deer_le4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 3.26 · 늑대 죽음 1 · 시작 E 0.41 · 10 단위 안 사슴 0.0
- T-C 위협 결정 2156: 마주 봄 0.439 · 도망 0.004 · 받기 0.032 · 동족 거리 위협 27.18 / 평소 29.16
- T-D 표범 먹잇감 (죽임/만남/D): boar 12/21768/-0.26 · buffalo 0/12067/-1.00 · deer 5/5307/0.08 · fox 18/7957/0.58 · wolf 17/17117/0.14
  - 무게 띠: 20-80kg 29/33177/0.08 · <20kg 18/9432/0.51 · >80kg 5/21607/-0.65
- T-H 죽임 표: boar>fox:counter 23 · boar>leopard:counter 1 · boar>wolf:counter 3 · buffalo>boar:gore 1 · buffalo>deer:gore 22 · buffalo>fox:counter 3 · buffalo>fox:gore 7 · buffalo>leopard:counter 2 · buffalo>wolf:counter 32 · buffalo>wolf:gore 31 · leopard>boar:bite 12 · leopard>deer:bite 5 · leopard>fox:bite 18 · leopard>wolf:bite 17 · wolf>boar:bite 44 · wolf>buffalo:bite 11 · wolf>deer:bite 17 · wolf>fox:bite 25 · wolf>leopard:bite 9
  - 표범 죽음 원인 {'bite': 9, 'counter': 3} · 은신처 안 물림 {'leopard>deer': 1, 'leopard>boar': 3, 'leopard>fox': 11, 'fox>deer': 1, 'fox>leopard': 5} · 물소 받기 HP/물소-일 {"deer": 0.1059, "wolf": 0.1203, "boar": 0.0097, "leopard": 0.0011, "fox": 0.0715}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 11530 중 칸에 없던 몫 0.1082 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 26.7 · 5 단위 안 몫 0.195 · 함께 덤빔 몫 0.003 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 14.0 · 5 단위 안 몫 0.381 · 함께 덤빔 몫 0.077 (현실은 혼자 — 보고만)

## C0-F9 속도 (시험 비행 묶음)

- buffalo: 1674 결정/초 · 10027008 결정 · 멈춤 target
- leopard: 1161 결정/초 · 5013504 결정 · 멈춤 target
- fox: 1147 결정/초 · 5013504 결정 · 멈춤 target
- wolf: 2773 결정/초 · 10006528 결정 · 멈춤 target

등록 문장: 사슴이 많은 세계에서 늑대가 어른 물소를 안 건드리는 것은 이상 신호가 아니다. '무리로 잡을 수 있나'는 장면 S1, '실제로 무리로 덤비나'는 buffalo_land 꼴 자연 세계로 본다.
