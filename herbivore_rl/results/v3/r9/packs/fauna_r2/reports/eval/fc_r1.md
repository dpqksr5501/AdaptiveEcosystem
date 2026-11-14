1 단계 평지 — 물소 물가는 2 단계, 첫 밤 결과는 정식 판정이 아님

- 만든 때 2026-11-13 11:37:30 · 설정 `configs/v3_r9_fauna.yaml` · 두뇌 {"deer": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\chain\\A\\deer_r1_18895744.npz", "wolf": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\chain\\A\\wolf_r1_6336960.npz", "boar": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\chain\\A\\boar_r1_6341376.npz", "buffalo": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\chain\\A\\buffalo_r1_6488448.npz", "leopard": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\chain\\A\\leopard_r1_4991616.npz", "fox": "C:\\kwon\\univ\\3-1\\GameContentsCapstoneDesign\\AdaptiveEcosystem\\herbivore_rl\\ckpt\\r9_fauna\\chain\\A\\fox_r1_5030208.npz"}
- 보고만 한다(판정 아님). 칸마다 사건 30 개 넘을 때만 비율을 적는다. 정의는 JSON 'defs'.

## 두뇌 판: learned
- deer mlp:deer_r1_18895744.npz · wolf mlp:wolf_r1_6336960.npz · boar mlp:boar_r1_6341376.npz · buffalo mlp:buffalo_r1_6488448.npz · leopard mlp:leopard_r1_4991616.npz · fox mlp:fox_r1_5030208.npz

### 자연 세계 N (base) — 10 세계 × 1350 결정 (74.0 초)

- 죽음(종: 물림·반격·굶음): deer 15·0·80 · wolf 0·0·9 · boar 1·0·24 · buffalo 0·0·10 · leopard 1·0·0 · fox 3·0·10
- T-A 덤빔 0 (끝나지 않음 0):
- T-C 위협 결정 411: 마주 봄 0.022 · 도망 0.002 · 받기 0.000 · 동족 거리 위협 42.21 / 평소 34.95
- T-D 표범 먹잇감 (죽임/만남/D): boar 0/3504/-1.00 · buffalo 0/1734/-1.00 · deer 3/20232/1.00 · fox 0/1656/-1.00 · wolf 0/1533/-1.00
  - 무게 띠: 20-80kg 3/24481/1.00 · <20kg 0/1665/-1.00 · >80kg 0/2513/-1.00
- T-H 죽임 표: leopard>deer:bite 3 · wolf>boar:bite 1 · wolf>deer:bite 12 · wolf>fox:bite 3 · wolf>leopard:bite 1
  - 표범 죽음 원인 {'bite': 1} · 은신처 안 물림 {'leopard>deer': 1} · 물소 받기 HP/물소-일 {"deer": 0.013, "wolf": 0.0, "boar": 0.0066, "leopard": 0.0, "fox": 0.0}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 56197 중 칸에 없던 몫 0.0012 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 22.9 · 5 단위 안 몫 0.204 · 함께 덤빔 몫 0.000 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 7.6 · 5 단위 안 몫 0.395 · 함께 덤빔 몫 0.011 (현실은 혼자 — 보고만)

### 자연 세계 N (buffalo_land) — 10 세계 × 1350 결정 (49.4 초)

- 죽음(종: 물림·반격·굶음): deer 0·0·2 · wolf 0·0·17 · boar 1·0·25 · buffalo 0·0·13 · leopard 1·0·2 · fox 1·0·12
- T-A 덤빔 2 (끝나지 않음 0):
  - pack2|adult|deer_le4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.00 · 늑대 죽음 0 · 시작 E 0.31 · 10 단위 안 사슴 0.0
  - pack3|adult|deer_le4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.00 · 늑대 죽음 0 · 시작 E 0.13 · 10 단위 안 사슴 0.0
- T-C 위협 결정 113: 마주 봄 0.177 · 도망 0.035 · 받기 0.000 · 동족 거리 위협 38.15 / 평소 36.31
- T-D 표범 먹잇감 (죽임/만남/D): boar 0/12122/— · buffalo 0/8740/— · deer 0/106/— · fox 0/3427/— · wolf 0/3615/—
  - 무게 띠: 20-80kg 0/8115/— · <20kg 0/3427/— · >80kg 0/16468/—
- T-H 죽임 표: wolf>boar:bite 1 · wolf>fox:bite 1 · wolf>leopard:bite 1
  - 표범 죽음 원인 {'bite': 1, 'starve': 2} · 은신처 안 물림 {} · 물소 받기 HP/물소-일 {"deer": 0.0057, "wolf": 0.0, "boar": 0.0012, "leopard": 0.0, "fox": 0.0}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 5473 중 칸에 없던 몫 0.0166 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 26.3 · 5 단위 안 몫 0.000 · 함께 덤빔 몫 0.000 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 3.5 · 5 단위 안 몫 0.570 · 함께 덤빔 몫 0.160 (현실은 혼자 — 보고만)

## 두뇌 판: rules
- deer rule:RULE_DEER · wolf rule:RULE_WOLF · boar rule:RULE_BOAR · buffalo rule:RULE_BUFFALO · leopard rule:RULE_LEOPARD · fox rule:RULE_FOX

### 자연 세계 N (base) — 10 세계 × 1350 결정 (83.2 초)

- 죽음(종: 물림·반격·굶음): deer 50·78·135 · wolf 6·3·0 · boar 11·0·9 · buffalo 2·0·14 · leopard 2·0·0 · fox 5·10·0
- T-A 덤빔 5 (끝나지 않음 5):
  - pack1|adult|deer_gt4: 덤빔 3 · 성공 0 (몫 —) · 늑대 HP 잃음 0.17 · 늑대 죽음 1 · 시작 E 0.79 · 10 단위 안 사슴 7.3
  - pack1|calf|deer_gt4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 0.10 · 늑대 죽음 0 · 시작 E 0.97 · 10 단위 안 사슴 2.0
  - pack2|adult|deer_gt4: 덤빔 1 · 성공 1 (몫 —) · 늑대 HP 잃음 0.11 · 늑대 죽음 0 · 시작 E 0.14 · 10 단위 안 사슴 0.0
- T-C 위협 결정 457: 마주 봄 0.392 · 도망 0.004 · 받기 0.033 · 동족 거리 위협 21.57 / 평소 26.14
- T-D 표범 먹잇감 (죽임/만남/D): boar 4/18111/-0.20 · buffalo 0/7870/-1.00 · deer 21/62268/0.09 · fox 3/1468/0.75 · wolf 6/18872/0.01
  - 무게 띠: 20-80kg 30/88370/0.26 · <20kg 3/4006/0.43 · >80kg 1/16213/-0.71
- T-H 죽임 표: boar>fox:counter 6 · boar>wolf:counter 1 · buffalo>deer:gore 78 · buffalo>fox:gore 4 · buffalo>wolf:counter 1 · buffalo>wolf:gore 1 · leopard>boar:bite 4 · leopard>deer:bite 21 · leopard>fox:bite 3 · leopard>wolf:bite 6 · wolf>boar:bite 7 · wolf>buffalo:bite 2 · wolf>deer:bite 29 · wolf>fox:bite 2 · wolf>leopard:bite 2
  - 표범 죽음 원인 {'bite': 2} · 은신처 안 물림 {'leopard>deer': 8, 'leopard>boar': 3, 'leopard>fox': 2, 'fox>deer': 5, 'fox>leopard': 2} · 물소 받기 HP/물소-일 {"deer": 1.5738, "wolf": 0.0452, "boar": 0.0127, "leopard": 0.0031, "fox": 0.0824}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 132076 중 칸에 없던 몫 0.1282 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 1.8 · 5 단위 안 몫 0.611 · 함께 덤빔 몫 0.039 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 1.3 · 5 단위 안 몫 0.625 · 함께 덤빔 몫 0.036 (현실은 혼자 — 보고만)

### 자연 세계 N (buffalo_land) — 10 세계 × 1350 결정 (80.0 초)

- 죽음(종: 물림·반격·굶음): deer 9·11·4 · wolf 10·27·0 · boar 32·1·12 · buffalo 3·0·12 · leopard 6·1·0 · fox 18·9·0
- T-A 덤빔 22 (끝나지 않음 4):
  - pack1|adult|deer_le4: 덤빔 10 · 성공 1 (몫 —) · 늑대 HP 잃음 1.44 · 늑대 죽음 4 · 시작 E 0.48 · 10 단위 안 사슴 0.3
  - pack2|adult|deer_le4: 덤빔 4 · 성공 0 (몫 —) · 늑대 HP 잃음 3.04 · 늑대 죽음 7 · 시작 E 0.75 · 10 단위 안 사슴 1.0
  - pack3|adult|deer_le4: 덤빔 4 · 성공 1 (몫 —) · 늑대 HP 잃음 2.76 · 늑대 죽음 5 · 시작 E 0.88 · 10 단위 안 사슴 0.0
  - pack4|adult|deer_le4: 덤빔 3 · 성공 1 (몫 —) · 늑대 HP 잃음 4.08 · 늑대 죽음 4 · 시작 E 0.76 · 10 단위 안 사슴 0.0
  - pack5+|adult|deer_le4: 덤빔 1 · 성공 0 (몫 —) · 늑대 HP 잃음 3.26 · 늑대 죽음 1 · 시작 E 0.41 · 10 단위 안 사슴 0.0
- T-C 위협 결정 885: 마주 봄 0.418 · 도망 0.006 · 받기 0.033 · 동족 거리 위협 30.19 / 평소 29.49
- T-D 표범 먹잇감 (죽임/만남/D): boar 6/7485/-0.09 · buffalo 0/5027/-1.00 · deer 1/2822/-0.47 · fox 11/3746/0.64 · wolf 10/11184/-0.03
  - 무게 띠: 20-80kg 14/19182/-0.27 · <20kg 11/4303/0.59 · >80kg 3/6779/-0.41
- T-H 죽임 표: boar>fox:counter 9 · boar>wolf:counter 2 · buffalo>boar:gore 1 · buffalo>deer:gore 11 · buffalo>leopard:counter 1 · buffalo>wolf:counter 14 · buffalo>wolf:gore 11 · leopard>boar:bite 6 · leopard>deer:bite 1 · leopard>fox:bite 11 · leopard>wolf:bite 10 · wolf>boar:bite 26 · wolf>buffalo:bite 3 · wolf>deer:bite 8 · wolf>fox:bite 7 · wolf>leopard:bite 6
  - 표범 죽음 원인 {'bite': 6, 'counter': 1} · 은신처 안 물림 {'leopard>boar': 3, 'leopard>fox': 7, 'fox>leopard': 5} · 물소 받기 HP/물소-일 {"deer": 0.1086, "wolf": 0.0938, "boar": 0.0118, "leopard": 0.0006, "fox": 0.0}
- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 4051 중 칸에 없던 몫 0.1572 (≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)
- T-M leopard: 가장 가까운 동족 중앙 27.1 · 5 단위 안 몫 0.018 · 함께 덤빔 몫 0.003 (현실은 혼자 — 보고만)
- T-M fox: 가장 가까운 동족 중앙 3.1 · 5 단위 안 몫 0.553 · 함께 덤빔 몫 0.024 (현실은 혼자 — 보고만)


등록 문장: 사슴이 많은 세계에서 늑대가 어른 물소를 안 건드리는 것은 이상 신호가 아니다. '무리로 잡을 수 있나'는 장면 S1, '실제로 무리로 덤비나'는 buffalo_land 꼴 자연 세계로 본다.
