"""V2 학습 환경 World — v1 `env/world.py` 에서 출발한 사본.

v1 파일은 언리얼에 연결된 계약(관측 7·행동 4)의 원본이라 한 줄도 바꾸지 않는다
(`Docs/RL_Policy/RL_V2_PLAN.md` 결정 3). V2 기능(속도·경계·기억·대담함·환경 상호작용)은
이 사본에 **스위치로** 붙인다. 스위치를 모두 끈 이 World 는 같은 시드에서 v1 World 와
결과가 완전히 같아야 한다 — `tests/test_env_v2.py` 가 고정한다.

기능 스위치는 버전 설정(`configs/v2*.yaml`)의 `features:` 블록이다(`env_v2/features.py`). 새 기능이 뽑는
난수는 기능마다 따로 둔 스트림 `self.feature_rng(name)` 에서만 뽑는다. v1 난수 호출 순서가 바뀌면
같은 시드의 세계가 조용히 달라지고, 기능끼리 스트림을 나눠 쓰면 기능 하나를 켜고 끌 때 다른 기능의
세계가 바뀌기 때문이다 (계획서 4.4, 4.8).

구현한 기능 (꺼진 기능의 코드 경로는 v1 과 같다):
- food_v (v2.0b, 계획서 4.9.1): 셀마다 식생 용량 V. 섭식이 V 를 깎고 재생은 cap0 대신 V 를 향한다.
  V 는 반감기 h 로 cap0 에 천천히 돌아온다. 스텝 순서는 `_food_v_step`, 통계는 `food_stats`·`food_cells`.
- speed (v2.1, 계획서 4.3·4.4·4.5): 행동이 5개가 된다(idx 4 = speed). 문턱으로 정지·걷기·뛰기를 정하고,
  상태가 v1 조향 속도의 크기, 섭식 배수, 대사를 정한다. 에너지 보상은 계수 하나로 순변화(#4)로 바꾼다.
  난수를 쓰지 않는다. 스텝 순서는 `_gait_step`, 통계는 `gait_stats`(v1 `stats()` 10열 밖).
- vigilance (v2.2, 계획서 4.2·4.3·4.4, #1·#5): 관측 하나(threat_recency)와 행동 하나(vigilance)가 붙는다.
  a_vig > 문턱이면 경계: 속력 0(speed 보다 우선), 섭식 배수 eat_mult(4.4 표 0), 대사는 정지 대사, 다음 관측의
  시야각 fov_deg(360°, 반경 see_r 그대로), heading 은 위협 쪽(ThreatDir). threat_recency·ThreatDir 는 개체별이고
  리스폰 때 초기화한다. 난수를 쓰지 않는다. 정의와 스텝 순서는 `_vigil_step`·`_perceive`, 통계는 `vigil_stats`.
  계수 threat_flee(10-03, 1-5 Gate E2b 보고용 #18 변형)는 0 이면 꺼져 있다(`_threat_flee_term`).
- vigil_window (v2.2r, 10-03 R2·수정 제안서 3.1 (나)): vigilance 위에 얹는 경계 재설계 스위치. '창' = 결정 때 포식자
  안 보임 & threat_recency > theta. action false 면 경계 행동 열을 빼고(관측 8 은 그대로, T1·L), window_only 면 경계가
  창 안에서만 효력이 있고(W′), look_back 이면 '정지 중이고 창 안이면 heading ← ThreatDir' 반사를 둔다(L). 난수를
  쓰지 않는다. 정의는 `_window_params`·`_look_back`, 통계는 `window_stats`. 끄면 v2.2 그대로다.
- daynight (v2.4, 계획서 4.9.2·4.2·#21): 세계마다 하루 길이 T 와 시작 위상 o 를 reset 때 자기 스트림에서 뽑고, 어둠 d
  (낮 0, 밤 1, 전환 앞뒤 박명은 선형)가 초식의 포식자 탐지 반경·섭식·정지 비경계 개체의 휴식 대사를 줄인다. 관측
  visibility·to_transition 두 칸이 붙는다. 동족 시야·관측 2 의 분모·포식자는 그대로다. speed 를 함께 켜야 한다.
  정의는 `_daynight_params`·`_daynight_update`, 통계는 `daynight_stats`. 낮 고정 세계(d = 0)는 v2.1 동역학 그대로다.
- pred_sleep (v2.4s, 10-07 사용자 결정 A안): daynight 위에 얹는다. 세계마다 야행성 비율 q 를 뽑고 포식자마다 확률 q 로
  야행성을 정한다(자기 스트림). 주행성 포식자는 어둠 d ≥ sleep_dark 면 잔다 — 멈추고 사냥하지 않고 초식 시야에 보이지
  않는다(굴에 있다). 깨어 있는 주행성 포식자는 twilight_slow 면 속력이 (1 − d) 배다. 야행성은 v2.4 그대로 움직인다.
  정의는 `_pred_sleep_params`·`_daynight_update`, 통계는 `pred_sleep_stats`.
- repertoire (v3 R0, 명세 `Docs/RL_Policy/RL_V3_R0_SPEC.md` 2·3절): speed·daynight 위에 얹는다(vigilance 와는 함께 켜지 않는다).
  행동이 한 열 'behavior'(정수 행동 번호. 정수가 아니면 거부)가 되고, v1 조향·보행 대신 행동 실행기(`env_v2/repertoire.py`:
  잠금·사건·결정 지연, 행동별 제어기)가 속도·보행·섭식·지각을 정한다. 장치: M1 정지 탐지(FREEZE·도착 HIDE·SLEEP 의 표적 선택
  체감 거리 × c_still), M2 놀람 정지, M4 잠 진입·기상, M5 GRAZE 고개 숙임(자기 탐지 반경), M6 행동별 은신 배수(은신처 안의
  웅크린 HIDE·GRAZE·SLEEP·그 밖, 계수 넷), SLEEP 시야 배수, SLEEP 전용 은신처 휴식 할인(daynight.rest_night 대신). 개체 행동
  상태(애니메이션 계약)는 스텝 뒤 훅 `World.behavior`·`beh_phase`·`beh_steps`·`beh_seq` 다. 난수를 쓰지 않는다(사건 결정
  지연은 세계 시드·슬롯·세대의 해시다). 추가 관측 9칸은 `rep_obs_extra` 가 늘 계산하고 obs_extra 가 true 일 때만 관측에
  붙는다. 통계는 `repertoire_stats`(슬롯별 전환·깜빡임 수는 `rep_slot_counts`). daynight_stats 의 휴식·먹기 열은 이 세계에서
  행동 기준이다(휴식 = 은신처 안 SLEEP, 먹기 = 먹이 셀의 GRAZE). v3 R1 은 결정 미리 보기 `rep_peek`(다음 스텝의 arbitrate 가
  요청을 읽는 개체, 순수 함수 — 학습·판정 마스크용, `env_v2/rep_policy.py`)를 더한다. 동역학은 바뀌지 않는다.
- threats (v3 R0, 명세 3절 M3·플레이어형 위협): daynight 위에 얹는다. reset 마다 잠행형 비율 p_stalk 를 뽑아 포식자마다
  잠행-돌진형을 정하고(잠행형은 근접형이다), 세계의 player_frac 에 플레이어형 위협 하나를 포식자 칸 끝에 더한다(밤에 자지
  않고 배회·잠행·돌진·휴식 모드를 바꾼다. 초식에게는 포식자와 같은 관측 칸으로 보인다). 자기 스트림 part 0(잠행형)·1(플레이어
  배치)·2(플레이어 모드)·3(플레이어 배회 선회)만 쓴다. 통계는 `threats_stats`.
  repertoire·threats 중 하나라도 켜면 포식자 스텝은 `_step_predators_v3` 다(v1 스트림 호출은 v2.4s 와 같은 모양).
- stare_down (v3 R2 M7, 명세 `Docs/RL_Policy/RL_V3_R2_SPEC.md` 2절): repertoire·threats 위에 얹는다. 잠행 위협(잠행형의 잠행
  단계, 플레이어의 잠행 모드)이 표적을 잠그고, 잠긴 표적이 얼어서 정면으로 spot_steps 이어 노려보면 잠행형은 멈춰 대치
  (STANDOFF)한 뒤 물러나고(BALK), 플레이어는 멈추지 않고 '들킴'이 되어 그동안 시작한 돌진이 느려진다. 스텝 순서는
  `_stare_check`(`_step_predators_v3` 의 C0), 훅은 `stare_by`·`pred_lock`·`spot_cnt`·`stalk_state`·`spotted_left`, 통계는
  `stare_stats`. 난수를 쓰지 않는다. spot_r 0 이고 target_lock false 면 끈 세계와 비트 동일이다.
- alarm (v3 R2 M8, 명세 3절): repertoire 위에 얹는다. FLEE·FREEZE·HIDE 로 바뀐 개체가 경보를 내고(A′, 위협이 보이면 홉 0,
  경보를 쥐고 있으면 중계), 잡힌 개체는 비명을 낸다. alarm_r 안의 동족이 E′ 에서 받는다(`env_v2/repertoire.py` alarm_*).
  관측 alarm_heard 한 칸(obs_extra 뒤 맨 끝)과 사건 E7 이 생긴다. 훅은 `alarm_level`·`alarm_hop`·`alarm_seq`·`alarm_pt`·
  `alarm_emit`·`entry_cause`·`alarm_e7`·`alarm_from`, 통계는 `alarm_stats`. 난수를 쓰지 않는다. alarm_r 0 이고 on_catch false 면 블록을
  건너뛴다(관측 칸은 0, E7 0회).
- realism_* (v3 현실성 1단계, 10-14 사용자 방향 — 팀 통합 레벨을 R1b 두뇌로 돌려 본 뒤 '쫓아오는 늑대가 뒤에 있어 안 보이니 도망을
  멈춤', '사냥 중인 늑대가 해가 지자 그 자리에서 잠듦'이 어색하다고 했다. 같은 날 갱신: '숨으면 못 먹게 하기보다 은신처에 먹이가
  적게'). 규칙 다섯은 따로 켜고 끄며 모두 repertoire 위에 얹는다. 블록이 없거나 enabled: false 면 그 규칙의 코드 경로를 타지 않아
  지금 세계와 비트 단위로 같다(tests/test_realism_v3.py — 이 단계 직전 커밋 626693c 의 코드와도 비교한다). 난수를 쓰지 않는다(지연은
  해시). 관측 18칸의 모양·값 범위·마스크 판(2)은 바뀌지 않는다. 계수 검사는 `_rz_*_params`, 통계는 `realism_stats`.
  늑대 식욕은 어느 규칙도 바꾸지 않는다(포만 없음, 쿨다운 pred_eat_cd 5 그대로 — 사용자 결정 '늑대는 과식하게 둔다'). 10-15 사람 결정으로
  R3 설정만 먹는 시간을 38스텝(약 5초, 제자리)으로 늘렸다 — 아래 'R3 세계' (j). 포만은 여전히 없다.
  (a) realism_vision — 사슴이 위협(포식자·플레이어)을 보는 시야각 threat_fov_deg(300° = 앞쪽 ±150°, 바로 뒤 60° 사각). 반경은 그대로
      (see_r × 밤 (1 − detect_night·d) × 행동 배수 GRAZE 0.6·SLEEP 0.3). 동족 시야각은 kin_fov_deg(120 = fov_deg 면 그대로).
      `_geometry` 의 보임 판정만 바뀐다. 판정 문턱 cos(시야각/2), 360° 면 각도 판정 없음(`_fov_cos`).
      현실 근거: 사슴은 눈이 머리 옆에 있어 수평 시야가 약 300~310°이고 바로 뒤 50~60°만 사각이다.
  (b) realism_hearing — 위협 m 의 '지난 스텝' 실제 이동 속력 s_m = |pred_vel_m| / herb_speed 와 그 스텝의 걸음새로 소리 반경을 정한다.
        s′_m = s_m                     (전력 걸음: 표적을 쫓는 추격형·원거리형, 돌진(POUNCE) 상태의 잠행형, 돌진(CHARGE) 모드의 플레이어 —
                                        훅 `pred_running`)
             = min(s_m, s_quiet)       (그 밖 — 배회·잠행·탈진·물러남·휴식·대치. roam_quiet false 면 늘 s′ = s)
        R_m  = 0                                                                     (s′_m < s_silent)
             = r_quiet + (r_loud − r_quiet) · clip((s′_m − s_quiet) / (s_loud − s_quiet), 0, 1)   (그 밖)
      사슴 i 와 깨어 있는 위협 m 의 실거리 ≤ min(R_m, 사슴 i 의 지금 탐지 반경)(cap_to_sight, 아니면 R_m)이고 R_m > 0 이면 방향과
      무관하게 '감지됨'이다 — 보임과 같은 칸에 들어간다(관측 pred_count·pred_dist·pred_approach, away·threat_recency, 사건 E1·E2).
      자는 위협(pred_sleep)은 빠진다. 1스텝 = 0.133 s, 1단위 ≈ 2 m. 출시 값(configs/v3_real1_*.yaml): s_silent 0.05, s_quiet 0.3,
      s_loud 1.0, r_quiet 2(4 m), r_loud 20(40 m = 낮 시야 반경). 예(속력 × herb_speed → R): 서 있음·대치·휴식 0 → 0 | 배회하는
      늑대(0.6~0.95, 배회 걸음) → 2 | 잠행 0.3·탈진 0.2 → 2 | 표적을 쫓는 추격형 0.6~0.95 → 9.7~18.7 | 원거리형 추격 0.36~0.57 → 3.5~8.9 |
      밤(속력 × 0.5)의 추격 0.3~0.48 → 2~6.5 | 잠행형 돌진 1.5·플레이어 돌진 1.3 → 20.
      현실 근거: 전력으로 쫓는 늑대는 발 구르는 소리·덤불 스치는 소리가 커서 사슴의 돌아가는 귀가 사방에서 잡는다. 돌아다니는 늑대는
      조용한 속보로 걷고 살금살금 다가오는 늑대는 아주 가까이 와야 들리며, 서 있거나 자는 늑대는 걸음 소리가 없다. (이 세계의 추격형은
      배회와 추격 속력이 같아서 — 단순화 — 속력만으로는 두 걸음새를 가를 수 없다. 그래서 roam_quiet 가 걸음새로 가른다.)
      cap_to_sight 는 현실 규칙이 아니라 학습 범위 보존 장치다(pred_dist ≤ visibility × 행동 배수라는 학습 때 결합 범위 유지).
  (c) realism_shelter — 은신처 원 안(포획 판정과 같은 위치 = 이번 스텝 초식 이동 뒤, `_in_cover`)의 사슴은 행동과 무관하게(GRAZE 로
      먹고 있어도) 잡히지 않는다. untargetable 이면 표적 고르기에서도 빠지고(stare_down 세계에서는 잠금도 추적 불가로 지운다),
      player_too 면 플레이어형 위협에도 같다. 은신 배수(M6)는 그대로 남지만 안전한 사슴에게는 효과가 없다.
      현실 근거: 빽빽한 덤불·바위틈 안에는 늑대가 몸을 들이밀어 덮칠 수 없다. 늑대는 닿을 수 없는 먹잇감을 오래 노리지 않고 떠난다.
  (e) realism_cover_food — 은신처 원과 조금이라도 겹치는 셀(`_cover_overlap_cells`, 훅 `World.cover_food_cell` — v1 의 재생 0.3배
      셀 `cover_cell`(셀 중심이 원 안)에 원 가장자리에 걸친 셀을 더한 것)의 먹이 용량 cap0 을 cap_frac 배, 재생률을 '밖 재생률'의
      regen_frac 배로 둔다(v1 cfg.food_cover_regen_mult 0.3 을 대신한다). 겹침으로 정하는 이유: 사슴은 자기 위치의 셀에서 먹고
      (`_cell_index`) 안전은 위치가 원 안인가(`_in_cover`)라서, 셀 중심으로 정하면 원 가장자리의 안전한 자리가 v1 그대로의 풍부한
      셀 위에 남는다(10-14 검토: 출시 두뇌 R1b·보정 시드 20000~20004 에서 원 안 섭취의 81% 가 그 가장자리 셀에서 나왔다). 겹침이면
      '원 안 = 먹이가 적은 셀'이 늘 성립한다. 밖 셀은 v1 그대로라 풍부한 패치가 밖에 남는다(먹이 패치 노이즈는 은신처 배치와 무관하다).
      `_build_world` 직후, food_v 의 식생 V 초기화 전에 적용한다. 출시 값 둘 다 0.15: 은신처 셀의 용량과 재생 속도가 밖의 15% 이고,
      먹힌 셀이 다시 차는 양은 밖의 약 2%(0.15 × 0.15)다. '숨으면 못 먹음' 규칙은 넣지 않는다 — 은신처 안 GRAZE 는 먹을 수 있고
      안전하다(웅크린 HIDE 가 먹지 않는 것은 R0 부터의 행동 정의라 그대로다). 가장자리 셀까지 바꾸므로 '끔과 같은 중립 값'은 없다
      (끄려면 블록을 끈다).
      현실 근거: 빽빽한 덤불·숲 그늘 밑은 햇빛이 모자라 풀이 적고 더디게 자라며, 트인 풀밭은 풀이 많지만 몸이 드러난다. 사슴이
      은신처에 몰리면 곧 바닥나서, 굶지 않으려면 위험을 무릅쓰고 밖으로 나가야 한다.
  (d) realism_night — pred_sleep 의 '주행성은 d ≥ sleep_dark 가 되는 스텝에 곧바로 잠' 대신 늑대마다 상태를 둔다(`_rz_night_update`).
      활동도 a_m ∈ {0..R}(R = ramp_steps)는 깨어 있으면 스텝마다 +1(R 에서 멈춤), '눕는 중'이면 −1 이고 0 이 되면 잠든다.
      눕기 시작: 깨어 있고, d ≥ sleep_dark 인 업데이트가 이어서 δ_m 번을 넘었고, 지난 포식자 스텝에 사냥 중(표적 있음, 잠행형 돌진·대치)
      이 아니고, 실거리 settle_r 안에 사슴이 없다. 눕는 중에 사냥이 시작되거나 사슴이 settle_r 안에 들어오면 멈추고 다시 일어난다.
      깜깜하면(결정 때 d ≥ hunt_dark) 깨어 있는 주행성 늑대는 새 사냥을 시작하지 않는다 — 지난 포식자 스텝에 사냥 중이던 늑대만 계속
      쫓고(표적·포획), 나머지는 표적·포획 판정에서 빠진다(`_step_predators_v3` 의 hunting). 계속 쫓는 늑대는 그 스텝에 보이는 가장
      가까운 개체를 표적으로 삼으므로 무리 안에서 표적을 바꿔 가며 쫓을 수 있다 — 보이는 표적이 한 스텝이라도 끊기거나 잡으면(쿨다운)
      그 사냥이 끝난다. 이것이 없으면 사슴이 많은 세계에서 늑대가 표적을 계속 새로 잡아 밤새 깨어 사냥한다(보정 시드 측정: 어둠
      업데이트의 49% 깨어 있음, 밤 피식 4.2배).
      깸: d < sleep_dark 가 된 뒤 δ_m 번 기다렸다가 a = 0 에서 깨어 오른다. 지연 δ_m = H(606, 세계 시드, 늑대 슬롯) mod (⌊spread·τ⌋ + 1),
      τ = 그 세계의 박명 폭(스텝). 속력 배수 = 자면 0, 깨어 있으면 max(1 − d (twilight_slow, 아니면 1), night_floor) × a_m / R.
      night_floor ≤ 1 − sleep_dark 로 검사하므로 해 질 녘·새벽(d < sleep_dark)의 (1 − d) 감속은 pred_sleep 그대로이고 하한은 해 진 뒤에만
      걸린다. reset 때 이미 밤이면 주행성은 자고 있다(a = 0).
      현실 근거: 늑대는 해 질 녘에 사냥을 마저 끝내고 주위가 조용해지면 걸음을 늦추다가 눕는다. 먹잇감이 가까이 있거나 쫓는 중이면
      눕지 않는다. 눈으로 사냥하는 주행성 사냥꾼은 깜깜해지면 새 사냥을 시작하지 않는다(쫓던 사냥은 마저 끝낸다). 새벽에는 하나씩
      깨어 몸을 풀며 천천히 움직이기 시작한다.
  난수(다섯 규칙 공통): 난수를 뽑지 않고 기능 스트림도 만들지 않는다. v1 스트림의 스텝당 호출 모양(배회 선회 M_base 개, v1 배치에
  원거리형이 있으면 원거리 판정 (M_base, N) 개)도 그대로다(은신처 안 사슴도 원거리 판정 난수는 뽑힌다) — 켠 세계에서 v1·기존 기능
  스트림 소비가 달라지는 것은 사건(사망·리스폰 `_respawn`, 플레이어 모드 전환 `_player_new_mode`)이 달라진 결과뿐이다.
- R3 세계 (10-14 사람 결정, 명세 `Docs/RL_Policy/RL_V3_R3_SPEC.md` 14절 — H6 추격 고정 처음부터 켬, H17 늑대는 은신처 원에 못 들어감,
  H18 지형 구역, H19 사슴은 지형을 관측하지 않음, H7 은신처 먹이 배수를 세계마다 뽑음, 사용자 '사슴 얼기를 없애'). 규칙마다 따로 켜고
  끄며 모두 repertoire 위에 얹는다. 끄면(블록이 없거나 선택 키가 끔 값이면) 1단계 세계와 비트 단위로 같다(tests/test_r3_world.py — 이
  단계 직전 커밋 8292856 의 코드와도 비교한다). 관측 18칸·마스크 판 2 는 그대로다. 통계는 `r3_stats`, 훅은 `pred_target`·`chase_tgt`·
  `terrain_cell`. 얼기(FREEZE)는 세계 규칙이 아니라 허용 목록(train.repertoire.allowed)에서 빠진다 — 행동 번호 계약(0 GRAZE … 4 SLEEP)은
  그대로이고 마스크가 FREEZE 를 늘 막는다(`env_v2/rep_policy.py`, 판정 롤아웃 `rep_learned` 은 모델 목록 ∩ 세계 목록). c_still(정지 탐지)은
  FREEZE·도착 HIDE·SLEEP 에 걸리는 규칙인데, R3 에서 FREEZE·SLEEP 은 막히고 도착 HIDE 는 늘 은신처 안(표적에서 빠짐)이라 실제로 쓰이지
  않는다(규칙은 그대로 둔다 — 고정한 표적에는 쓰지 않는다, 아래 (f)).
  (f) realism_chase (24) — 추격 고정. 고정을 쥘 수 있는 위협 = 사냥 중(쿨다운 0·깨어 있음·hunt_dark 규칙을 통과)이고, 추격형(근접·원거리)이거나,
      돌진(POUNCE) 상태의 잠행형이거나, player_too 면 돌진(CHARGE) 모드의 플레이어형 위협. stalk_phase 면 잠행형의 잠행 접근(배회 상태에서 표적
      쫓기)과 플레이어 잠행 모드도 쥔다. 위협 m 의 상태 chase_tgt(사슴 슬롯, −1 = 없음)·chase_lost(시야 밖 연속 스텝)·chase_pt(마지막으로
      본 자리). 포식자 스텝마다(위치 = 초식 이동 뒤, 포식자 이동 전 — 표적 고르기와 같은 때):
        1) 놓기: 쥔 상태가 아니면, 표적이 은신처 원 안이면(`_in_cover`, 포획 판정과 같은 위치), 또는 시야 밖이 lost_steps 스텝을 넘으면
           놓는다. 시야 = 실거리 ≤ pred_view_r & 위협 시야각 안(플레이어형 위협은 맵 전체를 본다). 보이면 chase_lost ← 0·chase_pt ← 위치,
           안 보이면 chase_lost + 1.
        2) 표적 고르기는 지금 규칙 그대로(체감 거리 최근접 — c_still·은신 배수·untargetable 포함).
        3) 쥔 위협은 고른 표적 대신 고정한 표적을 쓴다: 보이면 그 사슴 쪽으로, 거리 d_t = 실거리(c_still 은 새 표적을 고를 때만 쓴다 —
           얼어 있어도 늑대 눈에서 사라지지 않는다), 안 보이면 마지막으로 본 자리 쪽으로(겹치면 지금 heading), d_t = ∞(돌진·플레이어 돌진을
           새로 시작하지 않는다). 쫓는 중(has_target)으로 센다(걸음새 pred_running·밤잠 사냥 중 판정이 같은 값을 쓴다).
        4) 잠행형·플레이어 상태 전이(`_threat_motion`) 뒤, 쥘 수 있는 위협(전이 뒤 상태)이 고정이 없고 표적이 있으면 그 표적을 고정한다.
        5) 포획: 잡은 위협은 고정을 놓는다. 표적이 죽어 리스폰하면(`_respawn`) 고정을 놓는다.
      C++ 꼴(위협 m 하나, ThreatStep 의 표적 고르기 자리):
        bool bHold = bHunting && (Type==Chaser || (Type==Stalker && (State==Pounce || (bStalkPhase && State==Roam)))
                                  || (Type==Player && bPlayerToo && (Mode==Charge || (bStalkPhase && Mode==Stalk))));
        if (Lock.IsSet()) { const FPrey& K = Prey(Lock);
          if (!bHold || K.bInCover) Lock.Reset();
          else if (Type==Player || (Dist(m, K) <= PredViewR && FacingCos(m, K) >= PredFovCos)) { Lost = 0; LastSeen = K.Pos; }
          else if (++Lost > LostSteps) Lock.Reset(); }
        Pick(J, DT, bHasTarget);                                   // 지금 규칙
        if (Lock.IsSet()) { J = Lock; bHasTarget = true; DT = Lost == 0 ? Dist(m, Prey(Lock)) : INF;
                            Dir = Lost == 0 ? ToPrey : SafeDir(LastSeen - Q[m], H[m]); }
        StateStep(...);  bHold = (위 식, 전이 뒤 상태);  if (bHold && !Lock.IsSet() && bHasTarget) { Lock = J; Lost = 0; LastSeen = Prey(J).Pos; }
        if (bCaught) Lock.Reset();
      현실 근거: 늑대는 무리에서 한 마리를 골라 그 개체가 보이는 한 끝까지 쫓는다. 쫓기던 사슴이 얼어도 늑대 눈에서 사라지지 않고, 더
      가까운 옆 개체로 넘어가지 않는다. 시야에서 놓치면 마지막으로 본 자리까지 잠깐 더 달린다. 덤불 속으로 뛰어든 먹잇감은 포기한다.
      잠행 접근 중에는 가장 좋은 기회를 고르다가 돌진을 시작하면 그 한 마리에 매달린다(stalk_phase false, 명세 3-1 (f)).
  (c′) realism_shelter.block_predators (선택 키) — 늑대 은신처 진입 금지(H17). 막는 위협 = 포식자 전부와, player_too 면 플레이어형 위협.
      포식자 이동 뒤(벽 반사 전) 위치 q 가 은신처 원 k 안(|q − c_k| < r_k)이면 원 둘레 밖(반지름 r_k + WALL_EPS)으로 원의 중심에서 바깥쪽으로
      밀어낸다(q 가 중심과 겹치면 이전 위치 쪽). 원 순서대로 한 바퀴, 최대 WALL_PASSES 바퀴. 둘레 방향 성분은 남고 원 안쪽 성분만 없어져 원을
      따라 미끄러진다. 벽 반사·clip 뒤에도 어느 원 안이면(원이 맵 가장자리에 걸쳐 밀어낸 자리가 맵 밖이었거나, 겹친 원) 이전 위치 p 에서
      둘레가 가장 가까운 원의 바깥 법선 n 에 대해 이동 v 의 안쪽 성분만 뺀 v − min(v·n, 0)·n 로 간다(맵 안으로 자름, `_rz_wall_tangent`).
      그래도 원 안이면 이전 위치에 남는다(이전 위치는 늘 원 밖). 막힌 위협이 이번 스텝에 가려던 거리의 WALL_DEAD_FRAC(0.1)도 못 가면(원과
      맵 가장자리 사이 구석, 겹친 두 원 사이의 V 자 틈, 원 중심 쪽으로 곧장 부딪힘 — 막다른 곳) 돌아선다(heading ← 이번 이동의 반대 방향,
      맵 벽에서 튕기는 것과 같은 꼴). 그 밖에는 heading 은 가려던 방향 그대로다(목표를 보며 덤불을 돌아간다). 사슴은 그대로 드나들고, 은신처 안 사슴은 (c) 그대로 안전·표적 제외다. reset 때 원 안에 놓인 위협은 가장 가까운
      둘레 밖 후보(원마다 바깥쪽 반지름 방향 하나와 32 방향, 맵 안·모든 원 밖)로 옮긴다(난수 없음, v1 배치 난수는 그대로).
      플레이어형 위협은 맵 전체를 보므로 돌아서도 다음 스텝에 같은 사슴 쪽으로 되돌아와 막다른 곳에 계속 끼인다(10-14 검토, 탐색 시드
      32018: 잠행 모드 플레이어가 겹친 두 원 사이 V 자 틈에서 130스텝 넘게 멈췄다 — 잠행 모드는 200~400스텝 이어진다). 그래서 표적이 있는
      플레이어형 위협이 막다른 곳에 닿으면 그 접근을 그만둔다: 잠행 모드면 배회 모드로 바꾸고(남은 모드 길이 그대로, 난수 없음), 돌진 모드면
      돌진을 끝낸다(남은 돌진 0 — 이번 스텝 포획 판정 뒤 휴식). 늑대가 돌아서 시야를 잃고 표적을 놓는 것과 같은 꼴이다.
      C++ 꼴: for (pass < 3) for (k) if (|Q - C_k| < R_k) Q = C_k + (R_k + WallEps) * SafeDir(Q - C_k, P - C_k);
             WallReflectClip(Q); if (InsideAny(Q)) { Q = TangentSlide(P, V); if (InsideAny(Q)) Q = P; }
             if (bBlocked && |V| > Eps && |Q - P| < WallDeadFrac * |V|) Move = -V / |V|;     // 막다른 곳: 돌아선다
             if (bDead && Type==Player && bHasTarget) { if (Mode==Stalk) Mode = Wander; else if (Mode==Charge) PlayerLeft = 0; }
      현실 근거: 빽빽한 덤불·바위틈에는 늑대도 몸을 밀어 넣지 못해 덤불 가장자리를 따라 돌아간다. 사슴은 몸을 낮춰 파고든다.
  (c″) realism_shelter.wolf_margin (선택 키, 10-17 늑대 몸 여유, 기본 0) — 막는 위협에게만 원 반지름을 r_k + wolf_margin 으로 본다. 위 (c′)의
      원 안 판정(`_rz_inside_disc`)·밀어내기(`_rz_wall_push`, 반지름 r_k + wolf_margin + WALL_EPS)·접선 미끄러짐(`_rz_wall_tangent`, 둘레가 가장
      가까운 원 = |p − c_k| − (r_k + wolf_margin) 최소)·reset 옮기기(`_rz_wall_reset`)·통계 wall_inside_n 이 모두 이 반지름을 쓴다. 그래서 늑대
      중심은 늘 r_k + wolf_margin 밖에 있다. 사슴 쪽은 그대로다: 은신처 안전·표적 제외 (c)·도주 은신처 고르기·먹이는 원 반지름 r_k 를 쓴다.
      원 둘레와 r_k + wolf_margin 사이의 사슴은 원 밖이라 표적·포획 대상 그대로다(늑대가 포획 거리 안이면 잡는다). 0 이면 r_k + 0 = r_k 라
      10-16 과 비트 동일하다. 언리얼: 위협 Step 에 넘기는 원 목록의 반지름에 더한다(EcoWorldV3.h FWorldConfig::ShelterWolfMargin).
      C++ 꼴: Discs[3k + 2] = Cover[k].Radius + ShelterWolfMargin;   // 위 (c′) 의 R_k 가 이 값이다
      현실 근거: 늑대는 몸길이 약 1~1.5 m 인 동물이라(어림) 몸 중심이 빽빽한 덤불·바위 테두리에 몸 반쯤 길이보다 가까이 붙지 못한다.
      덤불을 따라 도는 늑대의 몸은 덤불 밖에 있다.
  (e′) realism_cover_food.frac_range (선택 키) — 세계마다 f = 하 + (상 − 하)·u, u = 자기 스트림 part 0 의 첫 난수 하나. 은신처 셀 용량 배수와
      재생 배수를 둘 다 f 로 둔다(H7). 폭 0 범위면 f = 하(1단계 고정 값과 같다).
      현실 근거: 덤불마다 밑풀 양이 다르다.
  (h) realism_terrain (25) — 지형 구역. 먹이 격자 셀(food_cell)마다 0 보통·1 눈·2 거친 땅(훅 `terrain_cell` (gw, gw) int8). 각 개체는 그
      스텝 이동 전 위치 셀(`_cell_index`)의 배수를 이동에 곱한다: 사슴은 이동 적용 직전 속도 v × mult_herb[땅](모든 행동), 위협은 밤잠 배수
      다음(곱 순서 (속력 × 밤 배수) × 땅 배수) 속력 × mult_pred[땅](플레이어형 위협은 mult_player). 대사·섭식은 보행 상태로 정해 그대로다
      (같은 힘으로 덜 간다). 시야·소리 규칙·먹이·은신처 안전·늑대 식욕은 바꾸지 않는다(소리 반경은 실제 이동으로 정하므로 눈에서 느려진
      늑대는 저절로 덜 들린다). 관측 칸은 없다(H19).
      만드는 법(`_rz_terrain_reset`, `_build_world` 뒤, 자기 스트림만): part 0 에서 4개 u0..u3 — 눈 목표 s = 0 (u0 < zero_p[0]), 아니면
      s = 하 + (상 − 하)·u1; 거친 땅 목표 r = 0 (u2 < zero_p[1]), 아니면 하 + (상 − 하)·u3. 눈 원판은 part 1, 거친 땅 원판은 part 2 에서
      은신처를 놓는 방식 그대로(셀 중심이 원판 안이면 칠함, 칠한 넓이가 목표에 닿을 때까지, 원판마다 중심 2개·반지름 1개, 최대
      max_patches). 거친 땅은 눈이 아닌 셀만 칠하고 넓이도 그 셀로 잰다. 목표 0 이면 원판을 놓지 않는다(넓이가 정확히 0). 놓는 자리는
      은신처·먹이와 독립이다.
      C++ 꼴: Speed *= NightMult; Speed *= TerrainMult[Type][Cell(Q)];   Vel *= HerbTerrainMult[Cell(P)];  (배치 난수는 옮기지 않고 격자를
      자료로 싣는다)
      현실 근거: 사슴은 몸무게에 비해 발굽이 작아 깊은 눈에 빠지고, 늑대는 넓은 발로 덜 빠진다. 돌밭·자갈 비탈은 둘 다 디딜 곳을 골라야
      해 느려진다(근거는 눈보다 약하다).
  (j) 늑대 먹는 시간 (10-15 사람 결정 '먹는 시간 주기 (약 5초)') — threats 블록의 선택 키 eat_in_place 와 v1 키 pred_eat_cd(overrides).
      늑대(추격형 근접·원거리, 잠행형 — 플레이어형 위협은 빼고)가 사슴을 잡은 스텝 t 에 쿨다운 cd ← pred_eat_cd = C 다(v1 그대로). 포식자
      스텝 첫머리에 cd 가 1 줄고 cd > 0 이면 사냥하지 않으므로, t+1 ~ t+C−1 의 C−1 스텝 동안 사냥하지 않고, t+C 스텝부터 다시 쫓고 잡는다.
      eat_in_place 가 true 면 그 C−1 스텝 동안 그 자리에 서서 먹는다(속력 0, heading 그대로 — 자는 늑대와 같은 꼴, 지형·밤잠 배수 앞).
      false 면 지금까지처럼 기본 속력으로 배회한다. 먹고 나면 곧바로 다시 사냥한다(포만 없음 — 사용자 결정 '늑대는 과식하게 둔다').
      R3 설정은 C = 38 이다: 5초 ÷ (1스텝 2/15초) = 37.5 → 반올림(0.5 는 올림) 38스텝 = 5.07초(그중 서서 먹는 37스텝 = 4.93초). 지난 값 C = 5
      (0.67초)는 언리얼 CVar eco.IntegratedV3.WolfEatSeconds 0.67 과 같다. 서 있는 늑대는 실제 이동이 0 이라 발소리가 없고(청각 (b)), 접근
      관측도 0 이다. 쿨다운 동안 추격 고정은 풀린다((f) 1). 난수를 쓰지 않는다(배회 선회 난수는 그대로 뽑고 쓰지 않는다 — v1 스트림 모양 그대로).
      C++ 꼴: if (bEatInPlace && Type != Player && Cooldown > 0) { Move = Head; Speed = 0; }   (상태 기계 뒤, 밤잠 배수 앞)
      현실 근거: 늑대는 잡은 먹잇감을 그 자리에서 뜯어 먹고, 먹는 동안에는 사냥하지 않는다. 굶주린 무리는 다 먹으면 곧 다음 사냥에 나선다.
- 통합 무대 integrated_stage (26, 10-15 사용자 '언리얼에서 돌리는 게 파이썬에서 돌리는 것과 얼마나 비슷한지 확인'): 언리얼 통합 v3 모드
  (AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoPolicyV3IntegratedSubsystem.cpp·EcoPolicyV3IntegratedProcessors.cpp, 문서
  Docs/RL_Policy/RL_V3_UNREAL_TRAINING_PLAN.md 4-5b)의 지역 무대 하나를 파이썬 세계 하나로 흉내 낸다. repertoire·threats 위에 얹는다. 키마다 따로
  켜고 끄며(끔 값 respawn true, 나머지 null) 모두 끈 블록은 끈 세계와 비트 동일이다. 같은 값만 설정으로 맞추는 것(맵 60, 늑대 2마리·속력 0.8,
  원거리형·야행성·플레이어 없음, 재생 배수 1, 하루 900스텝, 밤잠 점진화, 먹는 시간 38스텝 제자리, 얼기 막음)은 configs/v3_unreal_mirror.yaml 이
  맡는다. 이 블록은 설정으로 닫을 수 없는 차이만 다룬다.
  (k) respawn false — 부활 없음(C++ FWorldConfig::bRespawnDead = false, EcoWorldV3.h Step 의 G 단계). 훅 `World.alive` (N,) bool(끈 세계는
      None), `death_t`(죽은 스텝 끝 t, 산 개체 −1), `death_cause`(0 산, 1 잡힘, 2 굶음). 스텝 첫머리의 산 슬롯을 L 이라 하면 그 스텝에:
        이동 v ← 0·FREEZE 돌아보기 없음(¬L — 시체는 죽은 자리에 멈춘다, PrevPos = Pos), 늑대 표적·포획에서 뺌(vis·hit &= L — C++ Prey 는 산
        사슴 목록), 먹이 수요 0(섭식 배수 × L — 셀 수요 합에 0 을 더하므로 산 개체의 몫이 비트 단위로 같다), 에너지 그대로, 번식 &= L,
        굶음 = (E ≤ 0) & L & ¬잡힘(C++ Stats.Starved — 잡힌 개체는 포획으로만 센다), 보상 0(¬L), 관측 기하의 동족(kin_vis·분리 가중치)과 밤잠
        '사슴 근처'(realism_night settle_r) 판정의 열 &= L.
      스텝 끝 관측(8)은 아직 L 로 잰다 — 이번 스텝에 죽은 개체는 죽은 자리에서 동족으로 세어진다(C++ 관측 E 가 G 앞이다). 그 뒤 alive ← L & ¬done
      이고 리스폰(`_respawn`)·리스폰 관측을 하지 않는다(v1 리스폰 난수도 뽑지 않는다 — 언리얼은 시체를 2초 뒤 지우고 새 개체를 만들지 않는다).
      추격 고정(realism_chase)은 표적이 죽으면 리스폰 때처럼 놓는다. 경보(alarm)·노려보기(stare_down)는 죽은 개체를 빼는 규칙을 넣지 않아 함께
      켜지 못한다(읽을 때 실패). 슬롯 수 N 은 그대로라 배열 모양은 바뀌지 않는다. 죽은 행도 관측·정책·행동 상태(RepState)는 계속 계산되지만
      세계는 그 요청을 쓰지 않는다. 통계(stats·repertoire_stats 등)의 개체-스텝 분모는 죽은 행도 센다(통계 전용).
      학습(vec_env)은 빈 슬롯을 PPO 손실에서 뺄 마스크가 없어 이 세계를 받지 않는다(만들 때 실패). 번식으로 태어나는 다음 단계는 빈 슬롯(¬alive)에
      `_spawn_slots`(리스폰의 '새 개체 만들기' 부분, alive ← true)를 부모 곁 자리로 부르면 된다 — `_ist_bury` docstring.
  (l) ema_den — 피식 EMA 의 분모(C++ PredEmaDenominator = 무대에 처음 놓은 사슴 수). null 이면 N(지금 그대로, 사슴 수 = 슬롯 수인 거울에서는 같은 값).
  (m) day_offset — 시작 위상 o 를 이 값(mod T)으로 덮는다(daynight 스트림 뽑기 3개는 그대로, features.py 규칙 2). 0 = 언리얼(DayOffset 0, 팀 시계
      t = 0): d(0) = 0.5(새벽 전환), 450스텝 낮·450스텝 밤. realism_night 의 시작 상태는 이 위상으로 정한다(d = 0.5 ≥ sleep_dark 라 주행성 늑대는
      자고 시작한다 — 언리얼 로그의 첫 구간 '깸 2').
  (n) cover_layout 'quad' — v1 은신처 원(뽑기는 그대로)을 무대 1/4·3/4 지점 원 cover_count 개로 덮는다(EcoPolicyV3IntegratedSubsystem.cpp 우리 은신처
      자리). 원 k = 0..: 각 45° + 90°·k, 중심에서 0.25·S·√2(시도 12번 뒤 0.75 배), 시도 a 마다 ±15°·⌈a/2⌉ 돌린 자리 가운데 무대 안 여유 R + 1
      (2 m)과 앞 원과의 간격 2R + 2(4 m)을 지키는 첫 자리. R = clip(cover_r_frac × S, cover_r_min, cover_r_max)(C++ ExtraCoverRadiusUnits, 4~9 단위
      = 8~18 m). S = 60 이면 (45, 45)·(15, 45)·(15, 15)·(45, 15), R = 6, 넓이 12.6%. 지면 검사가 없어 S 60~110 에서는 늘 첫 시도에 놓인다.
      은신처 셀(v1 cover_cell, 셀 중심이 원 안 — C++ FFoodGrid CoverCell 과 같은 식)·재생률·cover_frac_actual 을 다시 정한다(`_build_world` 직후,
      현실성 (e)·food_v 초기화 전). 레벨 은신처는 넣지 않는다(통합 레벨 로그: 세 지역 모두 '레벨 0 + v3 4').
  (o) wolf_kinds 'alternate' — threats 스트림이 뽑은 구성(뽑기는 그대로)을 늑대 슬롯 짝수 = 잠행-돌진형, 홀수 = 근접 추격형, 모두 근접·주행성으로
      덮는다(C++ WolfSpecForOrdinal, 순번 = StableAgentId 순 — 로그상 Id 1 무대 (54, 54) 잠행, Id 2 (6, 6) 추격). threat_p_stalk 은 실제 잠행형 비율로
      바꾼다. 플레이어형 위협 칸은 바꾸지 않는다.
  (p) start_layout 'stage' — v1 시작 자리(뽑기는 그대로)를 C++ PlanStage 의 꼴로 덮는다(자기 스트림 part 0 만 쓴다). 무대 중심 c = S/2, 여유
      room = S/2 − deer_margin. 늑대(포식자 슬롯 0..M−1): 모서리 c + (±wolf_corner_frac·S) 를 (+,+)·(−,−)·(+,−)·(−,+) 순서로, 앞 늑대와 wolf_gap
      (C++ 1.5 × 28 m = 21 단위) 이상 떨어진 것만, 모자라면 c + U[−room, room]² 후보(최대 400번). 사슴(슬롯 0..N−1): c + U[−room, room]² 후보를
      max(64, 60·N) 번까지 — 모든 늑대에게서 deer_wolf_gap(28 m + 1 m = 14.5 단위) 이상, 앞 사슴과 deer_spacing(1.5 m = 0.75 단위) 이상인 것만.
      후보마다 x, y 두 난수. 다 못 놓으면 남은 개체는 v1 자리 그대로이고 훅 `stage_complete` 가 거짓이다(C++ bComplete). S = 60 이면 늑대는
      (54, 54)·(6, 6), 사슴은 [1.5, 58.5]².
  (q) head_layout 'golden' — 시작 방향을 사슴 슬롯 i 는 각 i·2.399963, 늑대 슬롯 m 은 (m + 2)·2.399963 rad 로 덮는다(C++ AEcoCreatureIntegrationSpawner
      의 yaw, 지역마다 순번 0 부터). 몇 스텝 안에 heading 이 속도 방향이 되므로 영향은 작다.
  닫지 못한 차이(설정 머리 주석에도 적는다): 난수열(C++ 자체 해시 난수 — 먹이 격자·배회 선회·시작 자리·결정 지연 키가 다르다, 분포는 같다),
  밤잠 지연 키(C++ 세션 시드·늑대 StableAgentId, 파이썬 세계 시드·슬롯), 지형 제약 이동(언리얼 FStepHooks — 비교 로그는 막힘 0), 팀 시계 동기·
  시체 2초 삭제(동역학과 무관), 경계 거리 KeepAway(커밋하지 않은 실험, 비교는 끔).
  C++ 꼴(부활 없음, 사슴 i 하나): if (!bAlive[i]) { Vel = 0; Want = 0; continue; }  bStarved = !bCaught && E <= 0;  ... 관측 E 뒤 bAlive[i] = !bDead;
- 야생 1단계(10-15 사용자 '야생 생태계 규칙을 만들어', '늑대 피해서 도망가다 굶어 죽는 게 말이 안 된다'. 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md,
  설정 configs/v3_wild1_mirror.yaml). 기능 셋, 모두 난수 없음. 시간 계수는 게임 하루 단위로 적고 스텝 = 반올림(일 × dn_period)이다. 관측 18칸은 그대로다.
  (w1) wild_reserve 지방 비축. 개체마다 R ∈ [0, 1](시작·새 개체 init). 비축 용량 C = reserve_days × dn_period × energy_drain(E 단위 — 걷기 대사만으로
      reserve_days 일을 버틴다). `step` 3) 에서 e_new 를 정한 뒤(산 개체만): e_new < 0 이면 모자람 −e_new 를 R·C 에서 꺼낸다(다 채우면 e_new = 0).
      e_new ≥ refill_e 이고 R < 1 이면 이번 스텝 먹은 에너지의 refill_frac 을(남은 빈자리 (1 − R)·C 까지) E 에서 R 로 옮긴다. 굶음 = E ≤ 0 이고
      R ≤ 0. 약함: 스텝 첫머리 E/max_energy < weak_e 인 개체는 이동 속도 × weak_speed(대사·섭식은 보행 그대로). 번식 규칙(E > 0.9 → 0.5)은 그대로다.
      현실 근거: 사슴은 배가 비어도 몸의 지방으로 여러 주를 버티고, 지방이 바닥나야 굶어 죽는다. 굶주린 사슴은 느리고 약해 늑대가 더 쉽게 잡는다.
      C++ 꼴: if (E < 0) { Take = min(-E / C, R); R -= Take; E = (Take * C >= -E) ? 0 : E + Take * C; }
              else if (E >= RefillE && R < 1) { Mv = min(RefillFrac * Gain, (1 - R) * C); E -= Mv; R += Mv / C; }  bStarved = E <= 0 && R <= 0;
  (w2) wild_satiation 늑대 포만. 포획 때(플레이어형 위협 말고) pred_sat ← 반올림(sat_days × dn_period). `_step_predators_v3` 첫머리 쿨다운을 줄인
      뒤 쿨다운 0 이고 pred_sat > 0 이면 이번 스텝은 배부름(훅 pred_sated): 사냥하지 않고(표적·포획 없음) pred_sat −1, 배회 속력 × rest_speed.
      배부른 늑대는 자지 않는 한 사슴에게 그대로 보인다. 현실 근거: 늑대는 먹이를 잡으면 몇 시간 먹고 그 곁에서 쉬며, 배가 고파져야 다시 사냥한다.
      C++ 꼴: Cd = max(Cd - 1, 0); bSated = Cd == 0 && Sat > 0; if (bSated) { --Sat; bHunting = false; Speed *= RestSpeed; }  on catch: Sat = SatSteps;
  (w3) wild_flight 도주 반사 거리(C++ 경계 거리 KeepAway 실험(EcoWorldV3.h FKeepAwayConfig)을 고친 판). 스텝 끝(관측·리스폰 뒤) 기하로 다음 스텝의
      덮기 wf_mode 를 정한다. '알아챔' = 이 사슴의 위협 보임(시야·청각, 관측과 같은 판정 — 기하 wf_pvis). 사냥 중인 늑대 = 깨어 있고 먹는 중(쿨다운)
      ·배부름(pred_sat)이 아닌 늑대. 다가옴 = 이 사슴을 표적으로 쫓음 또는 접근 관측 ≥ approach. 순서:
        은신처 원 안: 사냥 중인 늑대를 alert_r 안에서 알아챔이고 crouch 면 웅크림(HIDE 도착), 아니면 두뇌
        지난 도주: 사냥 중인 늑대가 실거리 safe_r 안에 있으면 계속 도주(쫓는 늑대는 돌아보며 안다), 아니면 풀림
        도주: 사냥 중인 늑대를 flight_r 안에서 알아챔, 또는 alert_r 안에서 알아챈 사냥 중인 늑대가 다가옴
        경계: 사냥 중인 늑대(rest_alert 면 쉬는·먹는 늑대도)를 alert_r 안에서 알아챔
      실행: 도주는 두뇌 요청 대신 FLEE(뛰기)로 들어가고 방향 = 실거리 safe_r 안 사냥 중인 늑대들 반대(거리 역수 가중 합). 그 방향 ±acos(shelter_cos)
      안에 가장자리 거리 shelter_r 안의 은신처가 있으면 가장 가까운 그 은신처 중심 쪽. 경계는 행동을 바꾸지 않는다 — 두뇌가 GRAZE 면 걸으며 먹고
      (섭식 걷기 배수) 방향 = n(GRAZE 조향 + alert_w·알아챈 늑대들 반대), 고개를 든다(자기 탐지 반경 배수 1). 두 방향 모두 무대 벽 wall_margin 안이면
      벽 쪽 성분을 지운다. 덮기(도주·웅크림)가 풀리면 잠금 0·미뤄 둔 사건 지움(두뇌가 곧바로 고른다).
      KeepAway 와 다른 점: 사냥 중인 늑대만 도주를 일으킨다(먹는·쉬는·자는 늑대는 경계만이거나 무시), 경계 중에도 먹는다(KeepAway 는 FLEE 걷기 —
      먹이 0), 알아챔은 사슴의 실제 감지(KeepAway 는 30 m 안이면 방향 무관), 도주 방향이 늑대 반대쪽 은신처를 고른다.
      현실 근거: 사슴은 포식자를 알아채면 먼저 고개를 들고 지켜보며 거리를 벌리고, 일정 거리 안으로 들어오거나 다가오면 달아난다. 사냥하지 않는
      포식자(쉬거나 먹는 늑대)에게는 덜 민감하다.
      10-16 선택 키(features.OPTIONAL_KEYS, 기본 false·0 = 위 그대로 — 사용자가 언리얼에서 보고 알린 '늑대가 먹기 시작하면 도망치던 사슴이 멈춘다'·
      '가장자리에서 늑대가 계속 잡아먹는다'):
        hold_awake: '지난 도주' 를 붙잡는 늑대가 사냥 중인 늑대 대신 깨어 있는 늑대 전부(사냥·먹기·배부름 — 자는 늑대 말고, 실거리 safe_r 안)다.
          도주 방향도 그 늑대들 반대다. 도주를 일으키는 것은 그대로 사냥 중인 늑대뿐이고, 은신처 원 안이면 도주는 풀린다(위 순서 첫 줄).
          현실 근거: 사슴은 포식자가 다른 사슴을 잡은 뒤에도 충분히 멀어질 때까지 달리고 멀리서 지켜본다
        edge_r > 0: 경계·도주 방향(은신처 쪽으로 정한 도주 말고)을 무대 벽 wall_margin 처리 앞에 `wf_edge_steer` 로 굽힌다 — 가장자리 edge_r
          안에서는 벽 쪽 성분을 벽을 따라가는 성분으로 돌리고(벽에 가까울수록 많이), 모서리(두 벽 모두 edge_r 안)에서 벽 쪽으로 가려 하면 늑대에게서
          더 멀어지는 쪽 벽을 따라 모서리를 빠져나온다. 현실 근거: 사슴은 달아날 길을 쓰고 막다른 곳으로 뛰어들지 않는다
- 야생 2단계(10-16 사용자 승인 '추천대로' — 늑대가 거의 못 잡는 세계를 사실감과 사냥 성공을 함께 올려 고친다. 명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md,
  설정 configs/v3_wild2_mirror.yaml = v3_wild1_mirror.yaml + 아래 규칙). 순서: 1 은신처 먹이 부족 → 2 늑대 무리·협동 사냥 → 3 장애물.
  1 은신처 먹이 부족: 새 규칙이 아니라 위 v3 현실성 (e) realism_cover_food 를 거울 세계에 켠다(cap_frac·regen_frac 0.15). 언리얼 FFoodGrid 가 같은 식이다
    (EcoWorldV3.h FShelterFoodConfig, 통합 모드 eco.IntegratedV3.ShelterFood).
  사냥 성공률(통계 전용, 동역학·난수와 무관 — `hunt_update`, `World.hunt_stats`): 사냥 한 번 = 한 늑대가 전력 걸음(추격형이 표적을 쫓음, 잠행형
    돌진 상태, 플레이어 돌진 — 발소리 훅 pred_running 과 같은 식)으로 이어 달린 스텝들. 전력 걸음을 시작한 스텝이 시작이고, 이 늑대가 잡은 스텝
    (전력 걸음이 끊긴 첫 스텝에 잡아도 그 사냥의 끝 모습이다)이 성공 끝, 잡지 못하고 전력 걸음이 끊긴 첫 스텝이 실패 끝이다. 추격형은 그 사이에
    표적이 바뀌어도(가장 가까운 보이는 사슴) 같은 사냥이다. 성공률 = 성공 ÷ 끝난 사냥. 사냥 중이 아닌 늑대가 잡은 수(사냥 밖 포획 — 등 뒤로 닿은
    사슴 등)는 따로 센다. 늑대만 센다(플레이어형 위협 말고). 야외 연구의 '사냥'(무리에 달려들기 시작 → 잡음·포기)과 같은 꼴이다.
    현실 근거: 늑대 사냥은 대부분 실패한다 — 사냥 한 번 성공률은 10~49%(Mech & Peterson 2003, Wolves: Behavior, Ecology, and Conservation 5장),
    옐로스톤 엘크는 혹독한 겨울 26%·포근한 겨울 15%(Mech 외 2001, J. Wildl. Manage. 65:998). 목표 띠 10~30% 로 둔다(어림).
  2 늑대 무리·협동 사냥 wild_pack (30, 10-17 사용자 '추천대로 끄고 2~4번 진행해' — 끈 것은 팀 무리 경보 연결뿐이다. 설정
    configs/v3_wild2_pack_mirror.yaml = v3_wild2_mirror.yaml(1 은신처 먹이 부족 켬) + 늑대 4 + 이 블록. 10-17 고침: 처음에는 그 말을 은신처 먹이
    부족을 끄라는 뜻으로 잘못 읽어 설정에서 뺐다 — 사용자의 결정은 '은신처는 안전하지만 먹이가 적다'(10-14·10-15)라 다시 켰다). 난수 없음. 늑대 수는 v1 키 rand.predator_count 다(거울 2 → 4, 두뇌 학습
    범위 2~12 안). 구성은 통합 무대 (o) 그대로다(슬롯 짝수 잠행형·홀수 추격형 — 4 마리면 둘씩). 포식자 스텝에서 표적 고르기·잠행형 상태 전이 뒤,
    먹기·배부름·밤잠 배수 앞에 정한다(`_pack_step`, 식은 `pack_goals`):
      앞장 = 늑대(플레이어형 말고)가 표적을 쫓으며 전력 걸음(추격형이 표적을 쫓음, 잠행형 돌진 중 표적 있음). 그 표적이 '쫓기는 사슴'이다.
      돕는 늑대 = 늑대이고 사냥 중(깨어 있음·먹기·배부름·탈진 아님·깜깜한 밤 새 사냥 규칙 통과)이며 전력 걸음이 아닌 늑대(표적이 없거나,
        잠행형이 표적에 살금살금 다가가는 중 — 동료의 추격에 합류한다).
      돕는 늑대마다 실거리 join_r 안의 쫓기는 사슴 가운데 가장 가까운 것(같으면 앞 슬롯 앞장)을 고른다. 없으면 지금 그대로(배회).
      도주 방향 u = 그 사슴의 이번 스텝 이동(이동 뒤 − 이동 전)의 단위벡터. 서 있으면 앞장 늑대에서 사슴 쪽.
      목표 자리: 가장자리 거리 e_k = |c_k − p| − r_k 가 0 < e_k ≤ door_r 이고 (c_k − p)·u / |c_k − p| ≥ door_cos 인 은신처 가운데 e_k 가 가장 작은 것
        (같으면 앞 번호)이 있으면 그 은신처의 문 c_k − (r_k + wolf_margin)·(c_k − p)/|c_k − p| (늑대가 설 수 있는 둘레, 사슴 쪽), 없으면 p + lead·u.
        무대 [0, S] 로 자른다.
      움직임: 목표 자리가 wait_r 밖이면 그쪽으로 기본 속력(배회·잠행 접근 대신), 안이면 멈춰(속력 0) 사슴 쪽을 본다(기다림 — 사슴과 겹치면
        heading 그대로).
        기다리는 늑대가 사슴을 보면 다음 스텝부터 지금 규칙대로 쫓거나 덮친다(잠행형은 체감 6 단위 안이면 돌진).
      은신처 진입 금지·몸 여유·밤잠·박명 감속·지형은 그대로 걸린다. 표적·포획·사냥 셈 규칙은 바꾸지 않는다.
      통계 `pack_stats`(앞장·도움·기다림·문 늑대-스텝, 협동 포획 = 다른 앞장 늑대도 쫓던 사슴을 잡은 수), 훅 pack_help·pack_wait·pack_door·pack_prey.
      C++ 꼴: EcoThreatModel.h PackPeek(사본으로 Step — 난수 없음) → PackGoals → Step 의 6b′ (In.bPackHelp 면 Move = PackDir, Speed = 기다림 ? 0 :
        BaseSpeed). 계수 join_r 은 처음 20 에서 60 으로 하나만 골랐다(명세 5절).
    현실 근거: 늑대 무리의 사냥 성공은 4 마리까지 늘고 그 위에서는 더 늘지 않는다(MacNulty 외 2012, Behav. Ecol. 23:75). 늑대는 먹잇감이 다니는
      길목에 따로 떨어져 기다린다(Gable 외 2024, Ethol. Ecol. Evol. 36(2) — 비버 매복). '먹잇감 쪽으로 가다 가까우면 다른 늑대에게서 벌어진다'는 두
      규칙만으로 둘러싸기가 생긴다(Muro 외 2011, Behav. Processes 88:192). 교대 추격(relay)은 넣지 않았다.
  3 세로 장애물 obstacles (12, 10-17 사용자 '추천대로 끄고 2~4번 진행해' — 10-14 에 자리만 둔 기능. 설정 configs/v3_wild2_obstacle_mirror.yaml =
    v3_wild2_pack_mirror.yaml + 이 블록). 자료 World.obstacles (K, 3) [x, y, r](단위, 열 이름 OBSTACLE_COLUMNS). 끄면 늘 (0, 3) 이고 어떤 판정도 읽지
    않는다(비트 동일). 다섯 자리:
      1) 배치 `_obstacles_reset`(`_build_world`·통합 무대 배치 뒤): fixed 가 있으면 그 원판(난수 없음 — 언리얼 무대에서 읽은 원판으로 도는 짝 비교),
         없으면 `obstacle_layout` — 자기 스트림 part 0 만 써서 나무 줄기 round(tree_per_ha × 무대 ha) 개, 그다음 바위 round(rock_per_ha × 무대 ha) 개.
         하나마다 (x, y) ~ U[0, S]², r ~ U[하, 상] 를 뽑고 중심이 은신처 원 안(|c − c_k| ≤ r_k)이거나 무대 벽에서 r + OB_EDGE_BODIES·body_r 안이면 다시
         뽑는다(OB_TRIES 번까지, 다 실패하면 건너뜀). 무대 벽은 실제 땅에 없는 학습 세계의 울타리라, 원판을 벽에 붙여 사슴이 끼는 막다른 구석(벽과 원판
         사이)을 만들지 않는다(벽 곁에 몸 하나 지나갈 틈). 언리얼 레벨 읽기는 벽에 걸친 원판도 그대로 넣는다(레벨의 나무를 지우면 사슴이 나무를 뚫는다).
         언리얼도 은신처 원 안에 중심이 있는 메시는 원판으로 넣지 않는다(은신처의 덤불·바위 장식이 은신처 원 자체다).
      2) 이동 `obstacle_slide`(사슴 `step` 1) 의 clip 뒤, 포식자 `_step_predators_v3` 의 이동 직후·은신처 밀어내기와 벽 반사 앞): 이동 p → q 가
         원판(반지름 R = r + body_r)에 처음 닿는 자리에서 멈추고(선분-원 교차의 가장 이른 t), 닿은 자리를 둘레 R + OB_EPS 로 옮긴 뒤 남은 이동의 안쪽
         성분만 뺀다(둘레를 따라 미끄러짐). 미끄러진 이동이 다른 원판에 닿으면 되풀이한다(OB_PASSES 번까지). 시작점이 원판 안이면 그 원판은 건너뛴다.
         마지막에(늑대는 은신처 밀어내기·벽 반사·자르기 뒤) 위치가 어느 원판(R) 안이면 이동 전 자리로 되돌린다. 늑대는 부딪혀 가려던 거리의
         WALL_DEAD_FRAC 도 못 가면 돌아선다(heading ← 가려던 이동의 반대, 은신처 막다른 곳과 같은 꼴). heading·적용 속도 훅은 가려던 방향 그대로다.
      3) 시선 `sight_blocked`(위협 보임 pvis `_geometry`, 포식자 표적 보임 vis `_step_predators_v3`): 두 점을 잇는 선분과 원 중심의 가장 가까운 거리가
         r 보다 작은 원판이 하나라도 있으면 눈으로 못 본다. 발소리(realism_hearing)는 가리지 않는다. 동족 시야는 가리지 않는다. block_sight false 면 없다.
         플레이어형 위협은 지금처럼 맵 전체를 본다. realism_chase·stare_down 의 시야는 가리지 않으므로 함께 켜지 않는다(켜면 읽을 때 실패).
      4) 먹이 `obstacle_food_factor`(`_obstacles_reset`, 은신처 먹이 부족 (e)·food_v 전): 셀마다 4 × 4 표본점((ix + (a + 0.5)/4)·cell, …) 가운데
         어느 원판(|q − c|² ≤ r²) 안인 몫 f 만큼 용량을 줄인다(cap ← cap × (1 − f), 먹이 ← min(먹이, cap)). no_food false 면 없다. 훅 ob_food_factor.
      5) 위치 `obstacle_push_out`(reset 끝 — 은신처 밖 밀어내기 뒤, `_respawn`): 원판(R) 안의 사슴·늑대를 가장 가까운 후보로 옮긴다. 후보 = 원판마다
         (중심 → 개체 쪽 둘레 R + OB_EPS 점) 하나와 OB_RING 8 방향(축·대각선, 성분 0·±1·±√½) 둘레 점. 무대 안이고 모든 원판 밖이고(늑대는 은신처
         막기를 켰으면 은신처 원(반지름 + 몸 여유) 밖) 인 후보 가운데 가장 가까운 것(같으면 앞). 없으면 그대로 두고 센다. v1 난수 호출은 그대로다.
    난수: 배치만 자기 스트림 part 0. 이동·시선·먹이·밀어내기는 난수가 없다. 통계 `obstacle_stats`.
    C++ 꼴: EcoThreatModel.h ObstacleSlide·SightBlocked·InsideAnyObstacle(위협 Step 1·4 표적 보임, 8 이동), EcoObservationV3.h FThreatInput::bOccluded
      (사슴 보임), EcoWorldV3.h FObstacleConfig·FFoodGrid::ApplyObstacleFood·ObstaclePushOut(C1 사슴 이동, 입양·리스폰). 언리얼은 무대 안 레벨의 충돌하는
      스태틱 메시(폴리지 인스턴스 포함)를 읽기만 해서 원판을 만든다(EcoPolicyV3IntegratedSubsystem ScanStageObstacles, 콘솔 변수 eco.IntegratedV3.Obstacles).
    현실 근거: 늑대에게 잡힌 엘크는 도망이 막히는 곳(강가·길가·깊은 눈)에서 더 많았다(Kauffman 외 2007, Ecol. Lett. 10:690). 숲은 그루가 빽빽해
      (온대 성숙림 1 ha 에 줄기 약 1200 그루, 가슴높이 단면적 34 m² — ESA Ecological Archives E094-195) 사슴·늑대가 줄기를 돌아 달리고 서로를 오래 보지 못한다.

행동·관측 수는 설정에서 읽는다: `action_names(cfg)`·`action_dim(cfg)`·`obs_names(cfg)`·`obs_dim(cfg)`, 세계마다
`World.act_names`·`World.act_dim`·`World.obs_names`·`World.obs_dim`. v1 4개(7개) 뒤에 켠 기능의 칸이 버전 순으로
붙는다(앞 버전을 건너뛰면 뒤 칸이 당겨진다, 계획서 4.1). 모듈 상수 `ACT_DIM`(4)·`OBS_DIM`(7)은 v1 수다.
"""

from __future__ import annotations

import math

import numpy as np

from . import repertoire as rep
from .features import Features, _check_name, _check_part, feature_stream, features_of, with_optional
from .steering import EPS, clamp_magnitude, normalize, steer

# 관측 열 인덱스 (§3.1). 이 순서가 언리얼 FEcoObservationFragment와 일치해야 한다.
OBS_FOOD_DENSITY = 0
OBS_PREDATOR_COUNT = 1
OBS_PREDATOR_DISTANCE = 2
OBS_KIN_COUNT = 3
OBS_ENERGY = 4
OBS_RECENT_PREDATION = 5
OBS_COVER_DISTANCE = 6
OBS_DIM = 7  # v1 관측 수 — 세계의 실제 관측 수는 World.obs_dim
OBS_NAMES_V1 = ("food_density", "pred_count", "pred_dist", "kin_count", "energy", "recent_predation", "cover_dist")
OBS_THREAT_RECENCY = 7  # vigilance 를 켠 세계의 threat_recency 열 (계획서 4.2 idx 7, 관측 첫 추가 칸)

ACT_DIM = 4  # forage, cohesion, flee_dist, cover (§3.2). v1 행동 수 — 세계의 실제 행동 수는 World.act_dim
ACT_NAMES_V1 = ("forage", "cohesion", "flee_dist", "cover")
ACT_SPEED = 4  # speed 를 켠 세계의 보행 행동 열 (계획서 4.3 idx 4)
# vigilance 행동 열은 speed 가 켜져 있으면 5(계획서 4.3), 아니면 4 다. 세계마다 World.act_names.index("vigilance")

# 보행 상태 번호 (계획서 4.4). replay_v2.GAIT_* 와 같다.
GAIT_STOP, GAIT_WALK, GAIT_RUN = 0, 1, 2

# food_stats 의 "하한에 붙은 셀": V/cap0 ≤ floor + 이 값. 휴식 회복이 훼손 뒤에 오므로 하한까지 깎인 셀도
# 스텝 끝에는 ρ·(1 − floor)만큼 위에 있다(반감기 300 에서 0.0021). 통계 정의이고 동역학 계수가 아니다.
FOOD_V_FLOOR_TOL = 0.01

# gait_stats 의 지표 정의 (계획서 6.2, 통계 정의이고 동역학 계수가 아니다).
# B1 거리 구간 [0, 0.25), [0.25, 0.5), [0.5, 1] (× see_r). "포식자 가까움" = 보임 & d_pred < B1_EDGES[1]·see_r
# (앞 두 구간, 계획서 6.2 의 d_pred < 0.5·see_r 이고 Gate E1 구간과 같다).
B1_EDGES = (0.25, 0.5)
# B2·hungry_frac 의 "배고픔" = 결정 때(스텝 전) energy < HUNGRY·max_energy (v1 react_hunger 와 같은 문턱).
HUNGRY = 0.5
# gait_stats 누적 히스토그램 모양: [실제 보행, 명령 보행, 포식자 거리 구간(안 보임 + B1 3구간), 배부름].
# 세계의 누적 배열은 앞에 경계 축 [비경계, 경계]가 붙은 (2,) + GAIT_HIST_SHAPE 다(vigilance 를 끄면 경계 칸은 0).
GAIT_HIST_SHAPE = (3, 3, 1 + len(B1_EDGES) + 1, 2)
# gait_stats() 열 순서. env_v2/rollout.py 가 speed 를 켠 세계의 행에 붙인다.
GAIT_STAT_COLUMNS = (
    "stop_frac", "walk_frac", "run_frac", "stall_frac",
    "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd",
    "hungry_frac", "starve_rate", "starve_share",
    "b1", "p_run_unseen", "p_run_d025", "p_run_d050", "p_run_d100",
    "b2", "p_stop_hungry", "p_stop_full",
    "b8", "b8_cmd", "intake_per_step", "drain_per_step",
)

# vigil_stats 의 지표 정의 (계획서 6.2 B3·B4·B5·B5′, 통계 정의이고 동역학 계수가 아니다).
# "최근 위협" = 결정 때 포식자 안 보임 & threat_recency > RECENT_THREAT (Gate E2 구간의 θ. 0.5 = 놓친 뒤 반감기 안).
# Gate E2(10-03, results/v2/e2/PREREG.md)는 θ 를 0.5 로 고정하고 통과했다(gate_e2.THETA 와 같다).
RECENT_THREAT = 0.5
# B5′ 의 recent_predation 상·하위 구간 (스텝 분위수, diagnose_v2.react_conditions 의 '위험 높음/낮음'과 같은 20%)
EMA_SPLIT_Q = 0.2
# vigil_stats 누적 히스토그램 모양: [구간 4(평시, 최근 위협·안 보임, 포식자 1마리 보임, 2마리 이상 보임),
# 결정 관측의 시야(0 = 기본 FOV, 1 = 경계 시야 — 직전 스텝에 경계), 배부름, 경계]
VIG_HIST_SHAPE = (4, 2, 2, 2)
# 시야와 무관한 기준 구간의 히스토그램 모양: [기준 구간 3(평시, 최근 반경 안·지금 밖, 지금 반경 안), 경계].
# '반경 안' = 결정 때 위치에서 거리 ≤ see_r 인 포식자가 있다(FOV 무시). 흔적은 threat_recency 와 같은 decay 다
VIG_TRUTH_SHAPE = (3, 2)
# vigil_stats() 열 순서. env_v2/rollout.py 가 vigilance 를 켠 세계의 행에 붙인다. 앞 28열은 1-4 첫 구현의 순서
# 그대로이고(rollout·diagnose 는 이름으로 읽는다), 뒤 16열은 10-03 검토에서 더한 360° 치우침 분리 열이다.
VIGIL_STAT_COLUMNS = (
    "vig_frac", "seg_seen_frac", "seg_recent_frac", "seg_calm_frac",
    "p_vig_seen", "p_vig_recent", "p_vig_calm", "b3", "b3_narrow",
    "b4", "b4_n", "b4_vig", "b4_vig_n",
    "b5", "p_vig_hungry", "p_vig_full",
    "b5p_pred", "p_vig_pc0", "p_vig_pc1", "p_vig_pc2", "b5p_ema",
    "b8_vig", "obs_wide_frac", "kin_narrow", "kin_wide", "pred_narrow", "pred_wide", "threat_mean",
    "p_vig_seen_narrow", "p_vig_pc0_narrow", "p_vig_pc1_narrow", "p_vig_pc2_narrow", "b5p_pred_narrow",
    "b4_narrow", "b4_narrow_n", "b4_wide", "b4_wide_n",
    "seg_near_truth_frac", "seg_recent_truth_frac", "p_vig_near_truth", "p_vig_recent_truth", "p_vig_calm_truth",
    "b3_truth", "b5p_truth",
)

# window_stats 누적 히스토그램 모양 (v2.2r, 수정 제안서 3.8 B3 정의): [구간 3(평시, 창 안, 포식자 보임), 배부름, 실제 정지,
# 경계]. 구간·배부름은 결정 때 상태, 창은 동역학과 같은 theta 로 정한다(vigil_stats 의 RECENT_THREAT 와 별개).
# 실제 정지 = 이번 스텝의 실제 보행이 정지(경계 포함, speed 를 끈 세계는 경계)다.
WINDOW_HIST_SHAPE = (3, 2, 2, 2)
# window_stats() 열 순서. env_v2/rollout.py 가 vigil_window 를 켠 세계의 행에 붙인다.
WINDOW_STAT_COLUMNS = (
    "win_frac", "p_stop_win", "p_stop_calm", "p_stop_win_full", "p_stop_calm_full", "b3_l",
    "p_stop_win_hungry", "p_stop_calm_hungry",
    "p_vig_win", "p_vig_win_full", "p_vig_win_hungry", "p_vig_calm_w",
    "look_frac", "look_win_frac",
)

# daynight_stats 위상 구간 (계획서 6.1-6, 2-5 행): 낮 d ≤ 0.2, 박명 0.2 < d < 0.8, 밤 d ≥ 0.8. d 는 박명 폭 정수 스텝의
# 유리수라 문턱 비교에 DN_TOL 여유를 둔다(관측 visibility 로 구간을 나누는 도구는 `daynight_seg_edges`).
DN_EDGES = (0.2, 0.8)
DN_TOL = 1e-9
# pred_sleep_stats() 열 순서 (v2.4s). env_v2/rollout.py 가 pred_sleep 을 켠 세계의 행에 붙인다.
PSLEEP_STAT_COLUMNS = ("pred_noct_frac", "pred_noct_n", "pred_asleep_mean")
# start_induce 의 유도 에너지 범위(max_energy 비율). 배고픔 문턱 HUNGRY(0.5) 아래다
INDUCE_ENERGY = (0.2, 0.5)
# 개체-스텝 히스토그램 [위상 3, 배부름 2, 결정 때 은신처 안 2, 실제 보행 3, 경계 2, 먹이 셀 2]. 먹이 셀 = 이번 스텝의
# 섭식 위치(이동 뒤) 셀의 기준 용량 cap0 > 0 (N5′ '먹이 셀', 10-06 사전 등록)
DN_HIST_SHAPE = (3, 2, 2, 3, 2, 2)
# B1·B2 위상 구간판 [경계 2, 위상 3, 명령 보행 3, 포식자 거리 구간 4, 배부름 2] (gait_stats 와 같은 정의, 위상 축만 더함)
DN_B_SHAPE = (2, 3, 3, 1 + len(B1_EDGES) + 1, 2)
# daynight_stats() 열 순서. env_v2/rollout.py 가 daynight 를 켠 세계의 행에 붙인다.
DAYNIGHT_STAT_COLUMNS = (
    "dn_period", "dn_offset", "dn_day_fixed", "dn_induced", "dark_mean", "frac_day", "frac_twi", "frac_night",
    "pred_rate_day", "pred_rate_twi", "pred_rate_night",
    "starve_rate_day", "starve_rate_twi", "starve_rate_night",
    "intake_day", "intake_twi", "intake_night", "intake_ratio_nd", "drain_day", "drain_night",
    "p_rest_cover_day", "p_rest_cover_night", "n1",
    "p_eat_night_hungry", "p_eat_night_full", "n5p", "p_eat_day_hungry", "p_eat_day_full",
    "p_stop_day", "p_stop_night", "p_run_day", "p_run_night", "p_cover_day", "p_cover_night",
    "p_stop_night_hungry", "p_stop_night_full",
    "b1_day", "b1_night", "b2_day", "b2_night", "n2",
)


# repertoire_stats 의 깜빡임 창: 행동 A → B → A 가 이 초 안에 되돌아오면 깜빡임(초안 지표 '3초 안 A-B-A'). 통계 정의다
FLICKER_SECONDS = 3.0
# repertoire_stats() 열 순서 (v3 R0). env_v2/rollout.py 가 repertoire 를 켠 세계의 행에 붙인다. 행동 이름은 repertoire.BEHAVIOR_NAMES
_BN = rep.BEHAVIOR_NAMES
REP_STAT_COLUMNS = (
    tuple(f"use_{b}" for b in _BN) + tuple(f"use_day_{b}" for b in _BN) + tuple(f"use_night_{b}" for b in _BN)
    + tuple(f"use_seen_{b}" for b in _BN) + tuple(f"use_unseen_{b}" for b in _BN)
    + tuple(f"pred_rate_{b}" for b in _BN) + tuple(f"starve_rate_{b}" for b in _BN)
    + ("seen_frac", "switch_per_sec", "flicker_rate", "decide_frac")
)
# 포식자 유형 번호 (threats). 원거리형은 유형이 아니라 pred_ranged 다(추격형 중 원거리)
PT_CHASER, PT_STALKER, PT_PLAYER = 0, 1, 2
# 잠행형 상태: 배회·잠행(표적 체감 거리 > stalk_dist), 돌진, 탈진. v3 R2 M7(stare_down): 대치(멈춰 마주 봄), 물러남
ST_ROAM, ST_POUNCE, ST_EXHAUST = 0, 1, 2
ST_STANDOFF, ST_BALK = 3, 4
# 플레이어 모드: 배회, 잠행 접근, 돌진, 휴식
PM_WANDER, PM_STALK, PM_CHARGE, PM_REST = 0, 1, 2, 3
# threats_stats() 열 순서 (v3 R0). 포획률은 개체-스텝당. catch_rate_chaser 는 근접 추격형, ranged 는 원거리 추격형
THREAT_STAT_COLUMNS = ("p_stalk", "stalker_n", "player_present", "catch_rate_chaser", "catch_rate_ranged",
                       "catch_rate_stalker", "catch_rate_player", "pounce_n", "pounce_hit", "player_charge_n")
# stare_stats() 열 순서 (v3 R2 M7, 명세 2-6). env_v2/rollout.py 가 stare_down 을 켠 세계의 행에만 붙인다(THREAT_STAT_COLUMNS 는
# 그대로). 수는 reset 뒤 누적 횟수다. 통계 정의이고 동역학 계수가 아니다
STARE_STAT_COLUMNS = ("standoff_n", "standoff_break_n", "blink_catch_n", "balk_n", "balk_share", "spotted_n",
                      "spotted_charge_n", "spotted_charge_catch_n", "lock_steps_mean", "stare_frac",
                      # 구현 검토 10-12 (보이는 지표, 동역학과 무관): 깨진 대치 중 표적이 FREEZE 를 그만둔 수(행동을 바꿔 깸 —
                      # 나머지는 눈맞춤·거리·추적 상실), 들킨 돌진·들키지 않은 플레이어 돌진의 포획 비율(H4 상한의 실제 효과)
                      "standoff_break_beh_n", "spotted_charge_catch_frac", "unspotted_charge_catch_frac")
# blink_catch_n 의 창: 대치가 깨진 뒤 이 스텝 안에 그 표적이 잡히면 '먼저 눈을 돌렸다' 포획으로 센다
BLINK_STEPS = 20
# alarm_stats() 열 순서 (v3 R2 M8, 명세 3-7·사전 등록 5절 '보이는 지표'). env_v2/rollout.py 가 alarm 을 켠 세계의 행에만 붙인다.
#   emit_h0·emit_h1·emit_h2: 홉별 방출 수(비명 포함, h2 는 홉 2 이상), cry_n: 비명 수, listen_per_emit: 방출당 후보로 들은
#   개체 수, alarm_frac: 관측 때 경보를 쥔(ttl > 0) 개체-스텝 비율, alarm_unseen_frac: 그중 위협이 안 보인 비율,
#   e7_n: 사건 E7 수, e7_switch_frac: E7 뒤 결정 지연 창(decision_jitter + 1 스텝) 안에 행동이 바뀐 비율(다른 사건·잠금 끝으로
#   바뀐 것도 들어가고, 결정했지만 GRAZE 를 유지한 것은 빠진다 — 글자 그대로의 뜻은 e7_decide_frac),
#   heard_entry_<행동>: 그 행동 진입 중 '들음' 원인(진입 원인 bit1 이고 bit0 아님) 비율, alarm_gap_mean: 개체마다 경보를 새로
#   쥔 순간(ttl 0 → > 0) 사이 간격의 평균(포화 확인), dir_n: 경보 방향을 받은 개체 수, dir_ok_pt·dir_ok_copy: 그중 실제
#   가장 가까운 (깨어 있는) 위협이 ±30° 안인 비율(점 방식·보낸 개체의 away 를 복사하는 비교 방식), wave_size_mean: 홉 0 방출
#   하나 뒤 WAVE_STEPS 안에 그 경보를 들은 원인으로 FLEE·FREEZE·HIDE 에 들어간 서로 다른 개체 수의 평균, heads_up_1s: 홉 0
#   방출자 alarm_r 안 개체 가운데 HEADS_UP_STEPS 뒤 FREEZE·FLEE 인 비율, false_alarm_frac: 본 위협으로 낸 홉 0(비명 제외) 중
#   그 위협이 직전 포식자 스텝에 사냥 중(표적이 있거나 돌진 중)이 아니었던 비율,
#   e7_decide_frac: E7 뒤 결정 지연 창 안에 결정 시점(decide)이 온 비율(명세 3-7 'E7 이 결정으로 이어진 비율'의 글자 그대로 판),
#   heads_up_1s_r16: heads_up_1s 를 사전 등록 5절 문구 그대로 반경 HEADS_UP_R16(16단위)으로 잰 값. 두 판은 구현 검토 10-12 에
#   더했다(사전 등록 변경 기록 10-12 (2) — 보고만, 판정에 쓰지 않는다)
ALARM_STAT_COLUMNS = ("emit_h0", "emit_h1", "emit_h2", "cry_n", "listen_per_emit", "alarm_frac", "alarm_unseen_frac",
                      "e7_n", "e7_switch_frac", "heard_entry_flee", "heard_entry_hide", "heard_entry_freeze",
                      "alarm_gap_mean", "dir_n", "dir_ok_pt", "dir_ok_copy", "wave_size_mean", "heads_up_1s",
                      "false_alarm_frac", "e7_decide_frac", "heads_up_1s_r16")
WAVE_STEPS = 20
HEADS_UP_STEPS = 8                  # 1초 = 7.5스텝 → 8스텝 뒤
HEADS_UP_R16 = 16.0                 # 사전 등록 5절 '홉 0 방출자 16단위 안'(글자 그대로 판)
DIR_COS = math.cos(math.radians(30.0))
# realism_stats() 열 순서 (v3 현실성 1단계). env_v2/rollout.py 가 realism_* 중 하나라도 켠 세계의 행에만 붙인다. 켜지 않은 규칙의 열은
# nan 이다. 통계 정의이고 동역학과 무관하다.
#   rear_seen_frac: 스텝 끝 관측(리스폰 전) 개체-스텝 중 위협이 눈으로 보이는데 기본 시야각(fov_deg 120)이었다면 하나도 안 보였을 비율
#   heard_only_frac: 위협이 감지됐는데 눈으로는 하나도 안 보인(들어서만 안) 비율
#   safe_frac: 포식자 스텝 개체-스텝 중 안전(은신처 원 안) 비율, safe_saved_n: 안전해서 포획 판정에서 빠진 '잡힐 거리' 개체-스텝 수
#   food_cap_kept: 마지막 reset 세계의 먹이 용량 합 / v1 용량 합(은신처 셀을 줄인 뒤), cover_intake_share: 섭취 중 은신처 원 안(섭식
#   위치)에서 먹은 몫
#   dark_awake_frac: 어둠(d ≥ sleep_dark) 업데이트의 주행성 늑대-업데이트 중 깨어 있는(눕는 중 포함) 비율, settle_n: 눕기 시작 수,
#   settle_abort_n: 눕다가 다시 일어난 수, onset_n: 잠든 수, block_deer_n·block_hunt_n: 누울 차례인데 사슴이 가까워·사냥 중이라 못
#   누운 늑대-업데이트 수, wake_n: 깬 수
REALISM_STAT_COLUMNS = ("rear_seen_frac", "heard_only_frac", "safe_frac", "safe_saved_n", "food_cap_kept",
                        "cover_intake_share", "dark_awake_frac", "settle_n", "settle_abort_n", "onset_n", "block_deer_n",
                        "block_hunt_n", "wake_n")
# r3_stats() 열 순서 (v3 R3 세계 — 추격 고정·늑대 은신처 진입 금지·은신처 먹이 배수 뽑기·지형). env_v2/rollout.py 가 그 규칙 중 하나라도
# 켠 세계의 행에만 붙인다. 켜지 않은 규칙의 열은 nan 이다. 통계 정의이고 동역학과 무관하다. 수는 reset 뒤 누적이다.
#   chase_lock_n: 새로 고정한 수, chase_held_n: 표적을 고른 뒤 고정을 쥔 위협-스텝, chase_lost_n: 그중 표적이 시야 밖(마지막 자리로 감),
#   chase_rel_cover_n·chase_rel_lost_n·chase_rel_state_n: 표적이 은신처 안·시야 밖 lost_steps 초과·쥘 수 없는 상태(쿨다운·탈진·잠·모드)
#   라서 놓은 수, chase_rel_catch_n: 잡아서 놓은 수(그중 고정한 표적을 잡은 수 chase_catch_own_n), chase_rel_dead_n: 표적이 다른 이유로
#   죽어(리스폰) 놓은 수
#   wall_push_n: 원 밖으로 밀어낸 위협-스텝, wall_slide_n: 밀어내도 원 안이라(원이 맵 가장자리에 걸침·겹친 원) 이전 위치에서 접선으로
#   미끄러진 위협-스텝, wall_stuck_n: 막다른 곳(막혀서 가려던 거리의 WALL_DEAD_FRAC 도 못 감)이라 돌아선 위협-스텝, wall_giveup_n: 그중 표적이
#   있는 플레이어형 위협이 접근을 그만둔 수(잠행 → 배회, 돌진 끝), wall_inside_n: 스텝 끝 원 안에
#   있는 막힌 위협-스텝(늘 0 이어야 한다), wall_reset_n: reset 때 원 밖으로 옮긴 위협 수(마지막 reset)
#   cover_food_cap·cover_food_regen: 마지막 reset 세계의 은신처 셀 용량·재생 배수(frac_range 면 뽑은 f)
#   snow_target·rough_target·snow_frac_actual·rough_frac_actual·snow_patches·rough_patches: 마지막 reset 세계의 지형 목표·실제 셀 비율·원판 수
#   deer_n_<땅>: 이동 전 위치 셀의 땅별 사슴-스텝, catch_<땅>_n: 잡힌 순간(초식 이동 뒤) 사슴 위치의 땅별 포획 수, catch_rate_<땅> = 포획 /
#   그 땅의 사슴-스텝(분모 0 이면 nan), pounce_<땅>_n·pounce_hit_<땅>_n: 잠행형 돌진 시작(돌진 표적 사슴의 땅)·그 돌진의 포획
TERRAIN_NAMES = ("normal", "snow", "rough")
TERRAIN_NORMAL, TERRAIN_SNOW, TERRAIN_ROUGH = 0, 1, 2
R3_STAT_COLUMNS = (("chase_lock_n", "chase_held_n", "chase_lost_n", "chase_rel_cover_n", "chase_rel_lost_n", "chase_rel_state_n",
                    "chase_rel_catch_n", "chase_catch_own_n", "chase_rel_dead_n",
                    "wall_push_n", "wall_slide_n", "wall_stuck_n", "wall_giveup_n", "wall_inside_n", "wall_reset_n",
                    "cover_food_cap", "cover_food_regen",
                    "snow_target", "rough_target", "snow_frac_actual", "rough_frac_actual", "snow_patches", "rough_patches")
                   + tuple(f"deer_n_{t}" for t in TERRAIN_NAMES) + tuple(f"catch_{t}_n" for t in TERRAIN_NAMES)
                   + tuple(f"catch_rate_{t}" for t in TERRAIN_NAMES) + tuple(f"pounce_{t}_n" for t in TERRAIN_NAMES)
                   + tuple(f"pounce_hit_{t}_n" for t in TERRAIN_NAMES))
# realism_shelter.block_predators: 밀어낸 위치의 반지름 여유(단위 — 2 µm, 둘레 위 반올림으로 원 안 판정이 되지 않게), 밀어내기 바퀴 수,
# reset 때 옮길 후보의 원마다 방향 수
WALL_EPS = 1.0e-6
WALL_PASSES = 3
WALL_RING = 32
# 막다른 곳 판정: 원에 막힌 위협이 이번 스텝에 가려던 거리의 이 몫도 못 가면 돌아선다(둘레를 따라 비스듬히 미끄러지는 늑대는 이보다 많이
# 간다 — 부딪힌 각이 원 법선에서 약 6° 안일 때만 걸린다)
WALL_DEAD_FRAC = 0.1
# realism_night 의 늑대별 잠·기상 지연 해시의 첫 입력. repertoire.JITTER_TAG(505)·rollout._SALT(101·202·303·404)와 겹치지 않는다
NIGHT_TAG = 606
# 야생 2단계 3 세로 장애물(모듈 docstring '야생 2단계' 3): World.obstacles 의 열(끈 세계는 늘 비어 있다)
OBSTACLE_COLUMNS = ("x", "y", "r")
OB_PASSES = 3            # 미끄러짐 되풀이 수
OB_EPS = 1.0e-6          # 닿은 자리를 둘레 밖으로 옮기는 여유(단위)
OB_TRIES = 20            # 배치: 중심이 은신처 원 안이거나 무대 가장자리에 붙으면 다시 뽑는 수
OB_EDGE_BODIES = 2.0     # 배치: 원판 중심은 무대 벽에서 r + 이 배수 × body_r 밖 (벽 곁에 몸 하나 지나갈 틈 — 막다른 구석을 만들지 않는다)
OB_SAMPLES = 4           # 먹이: 셀 한 변의 표본점 수(셀마다 4 × 4)
OB_UNIT_M = 2.0          # 1 단위 = 2 m (무대 ha 계산)
_OB_S = math.sqrt(0.5)
# 밀어내기 후보 방향 8 개(축·대각선). 삼각함수 없이 정해 C++ 와 비트 단위로 같다(EcoWorldV3.h kObstacleRing)
OB_RING = ((1.0, 0.0), (_OB_S, _OB_S), (0.0, 1.0), (-_OB_S, _OB_S), (-1.0, 0.0), (-_OB_S, -_OB_S), (0.0, -1.0), (_OB_S, -_OB_S))


WORLD_PARAM_KEYS = ("world_size", "predator_count", "pred_speed_mult", "ranged_frac", "cover_frac", "food_regen_mult")


def world_params(cfg, seed: int) -> dict:
    """세계 시드 하나가 정하는 무작위화 매개변수(`World.reset` 이 같은 순서로 뽑는 값)를 세계를 만들지 않고 낸다.

    reset 의 v1 스트림 `default_rng(seed)` 앞 여섯 번 뽑기와 같다: 크기, 포식자 수 M, 포식자 속도 배수, 원거리형 비율,
    은신처 비율 목표, 먹이 재생 배수. 학습 세계 균형 추출(`env_v2/vec_env.py`, S1-a 10-04 결정)과 진단이 쓴다.
    reset 의 뽑는 순서를 바꾸면 이 함수도 같이 바꿔야 한다(`tests/test_world_sampling_v2.py` 가 맞는지 본다).
    """
    rd = cfg.rand
    r = np.random.default_rng(int(seed))
    size = float(r.uniform(*rd["world_size"]))
    m = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
    psm = float(r.uniform(*rd["pred_speed_mult"]))
    rf = float(r.uniform(*rd["ranged_frac"]))
    cf = float(r.uniform(*rd["cover_frac"]))
    fr = float(r.uniform(*rd["food_regen_mult"]))
    return dict(zip(WORLD_PARAM_KEYS, (size, m, psm, rf, cf, fr)))


def action_names(cfg) -> tuple[str, ...]:
    """설정(또는 `Features`)의 세계가 받는 행동 이름. 순서 = 행동 열 번호 (계획서 4.3).

    v1 4개 뒤에 켠 기능의 행동이 버전 순으로 붙는다: speed(v2.1), vigilance(v2.2). 앞 기능을 끄면 뒤 칸이
    당겨진다(speed 없이 vigilance 만 켜면 vigilance 가 열 4). 한번 정한 순서는 바꾸지 않는다.
    vigil_window(v2.2r)를 켜고 action 이 false 면 vigilance 열이 없다(관측 threat_recency 는 그대로).
    repertoire(v3)를 켜면 행동은 한 열 'behavior'(정수 행동 번호를 float 로. env_v2/repertoire.py)뿐이다.
    """
    f = cfg if isinstance(cfg, Features) else features_of(cfg)
    if f.enabled("repertoire"):
        return ("behavior",)
    names = ACT_NAMES_V1
    if f.enabled("speed"):
        names = names + ("speed",)
    if f.enabled("vigilance") and (not f.enabled("vigil_window") or f.params("vigil_window")["action"]):
        names = names + ("vigilance",)
    return names


def action_dim(cfg) -> int:
    """설정의 세계가 받는 행동 수. v1·v2.0·v2.0b 4, speed 를 켜면 5, vigilance 까지 켜면 6(v2.2r action false 면 5)."""
    return len(action_names(cfg))


def obs_names(cfg) -> tuple[str, ...]:
    """설정(또는 `Features`)의 세계가 내는 관측 이름. 순서 = 관측 열 번호 (계획서 4.2).

    v1 7개(이름은 diagnose_v2.OBS_NAMES 와 같다) 뒤에 켠 기능의 관측이 붙는다: threat_recency(v2.2),
    visibility·to_transition(v2.4). 앞 기능을 끄면 뒤 칸이 당겨진다 — v2.1 위의 v2.4 는 visibility 가 idx 7,
    to_transition 이 idx 8 이다(계획서 4.2 의 9·10 은 v2.2·v2.3 을 모두 했을 때 번호이고, idx 7~10 은 V2a 에서 확정한다).
    도구는 칸을 번호가 아니라 이름으로 찾는다.
    repertoire(v3)의 obs_extra 가 true 면 뒤에 9칸(`repertoire.OBS_EXTRA_NAMES`)이 붙는다(R0 설정은 false). 그 위에 alarm(v3 R2
    M8)을 켜면 맨 끝에 alarm_heard 한 칸이 붙는다(18 → 19칸, 앞 칸 번호는 그대로).
    """
    f = cfg if isinstance(cfg, Features) else features_of(cfg)
    names = OBS_NAMES_V1
    if f.enabled("vigilance"):
        names = names + ("threat_recency",)
    if f.enabled("daynight"):
        names = names + ("visibility", "to_transition")
    if f.enabled("repertoire") and f.params("repertoire").get("obs_extra") is True:
        names = names + rep.OBS_EXTRA_NAMES
        if f.enabled("alarm"):
            names = names + (rep.OBS_ALARM_NAME,)
    return names


def obs_dim(cfg) -> int:
    """설정의 세계가 내는 관측 수. v1·v2.0·v2.0b·v2.1 7, vigilance 를 켜면 8, v2.1 + daynight 9."""
    return len(obs_names(cfg))


def _num(feature: str, key: str, x) -> float:
    """기능 계수 하나가 유한한 숫자인지 본다(bool 은 거부)."""
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) or not math.isfinite(x):
        raise ValueError(f"features.{feature}.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
    return float(x)


def _vigil_params(p: dict, base_fov_deg: float) -> dict:
    """vigilance 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    - threshold ∈ [0, 1]: a_vig > threshold 면 경계 (계획서 4.3 "0.5 를 넘으면", 같으면 경계가 아니다)
    - decay ∈ [0, 1]: threat_recency 의 스텝당 감쇠 계수. 반감기 = ln 0.5 / ln decay 스텝 (0 이면 '지금 보임'과 같다)
    - eat_mult ≥ 0: 경계 중 섭식 배수(`_eat` 의 want 에 곱한다)
    - fov_deg ∈ [fov_deg(v1), 360]: 경계한 스텝 뒤 관측의 시야각. 360 이면 각도 판정 없이 반경 see_r 안 전부다
      (cos(180°) = −1 과의 비교는 반올림으로 정반대 방향을 놓칠 수 있어 −inf 로 둔다)
    - threat_flee ≥ 0: 10절 #18 조향 변형 항의 배수(`_threat_flee_term`). 0 이면 항이 없다(1-4 구현과 비트 단위로
      같다 — `steer` 에 아무것도 더하지 않는다). Gate E2b 의 '계속 뛰기 + 위협 반대 항' 보고 팔만 1 로 둔다
    """
    th = _num("vigilance", "threshold", p["threshold"])
    dec = _num("vigilance", "decay", p["decay"])
    eat = _num("vigilance", "eat_mult", p["eat_mult"])
    fov = _num("vigilance", "fov_deg", p["fov_deg"])
    tf = _num("vigilance", "threat_flee", p["threat_flee"])
    if not 0.0 <= th <= 1.0:
        raise ValueError(f"features.vigilance.threshold 는 [0, 1] 이어야 한다(행동은 sigmoid 뒤 값). 받은 값: {th}")
    if not 0.0 <= dec <= 1.0:
        raise ValueError(f"features.vigilance.decay 는 [0, 1] 이어야 한다. 받은 값: {dec}")
    if eat < 0.0:
        raise ValueError(f"features.vigilance.eat_mult 는 0 이상이어야 한다. 받은 값: {eat}")
    if not float(base_fov_deg) <= fov <= 360.0:
        raise ValueError(f"features.vigilance.fov_deg 는 기본 시야각 {base_fov_deg} 이상 360 이하여야 한다. 받은 값: {fov}")
    if tf < 0.0:
        raise ValueError(f"features.vigilance.threat_flee 는 0 이상이어야 한다. 받은 값: {tf}")
    wide_cos = -math.inf if fov >= 360.0 else math.cos(math.radians(fov) * 0.5)
    half_life = math.log(0.5) / math.log(dec) if 0.0 < dec < 1.0 else (0.0 if dec == 0.0 else math.inf)
    return dict(threshold=th, decay=dec, eat_mult=eat, fov_deg=fov, threat_flee=tf, wide_cos=wide_cos,
                half_life=half_life)


def _window_params(p: dict, f: Features) -> dict:
    """vigil_window 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (v2.2r, 수정 제안서 3.1 (나)).

    - action (bool): 경계 행동 열이 있나. false 면 행동에서 vigilance 열을 빼고(`action_names`) 경계는 일어나지 않는다.
      관측 threat_recency·ThreatDir 갱신(`_perceive`)은 vigilance 그대로다 — T1(관측 8만)·L(반사)
    - window_only (bool): 경계가 창 안 개체에서만 효력이 있다(W′). 창 밖에서 a_vig > threshold 여도 경계가 아니고
      speed 가 보행을 정한다. action 이 true 여야 한다
    - look_back (bool): 반사 돌아보기(L). 이번 스텝의 실제 보행이 정지이고 창 안이면 heading ← ThreatDir(`_look_back`).
      정지를 speed 가 정하므로 speed 를 켜야 한다
    - theta ∈ [0, 1): 창 문턱. 창 = 결정 때 포식자 안 보임(관측 1 = 0) & threat_recency > theta. Gate E2 의 θ 0.5
      (RECENT_THREAT, 놓친 뒤 13스텝)를 적는다
    vigilance 를 켜야 한다(threat_recency·ThreatDir·경계 계수가 거기 있다).
    """
    if not f.enabled("vigilance"):
        raise ValueError("features.vigil_window 는 vigilance 를 함께 켜야 한다(threat_recency·ThreatDir 가 vigilance 에 있다)")
    out = {}
    for key in ("action", "window_only", "look_back"):
        if not isinstance(p[key], bool):
            raise ValueError(f"features.vigil_window.{key} 는 true/false 여야 한다. 받은 값: {p[key]!r}")
        out[key] = p[key]
    th = _num("vigil_window", "theta", p["theta"])
    if not 0.0 <= th < 1.0:
        raise ValueError(f"features.vigil_window.theta 는 [0, 1) 이어야 한다(threat_recency 는 보이면 1). 받은 값: {th}")
    out["theta"] = th
    if out["window_only"] and not out["action"]:
        raise ValueError("features.vigil_window.window_only 는 action: true 일 때만 쓴다(경계 행동 열이 없으면 효력도 없다)")
    if out["look_back"] and not f.enabled("speed"):
        raise ValueError("features.vigil_window.look_back 은 speed 를 함께 켜야 한다(반사 조건 '정지'를 speed 가 정한다)")
    return out


def _speed_params(p: dict) -> dict:
    """speed 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사하고 상태별 표를 만든다. 기본값은 없다.

    - thresholds [t_walk, t_run]: 0 ≤ t_walk ≤ t_run ≤ 1. a < t_walk 정지, a < t_run 걷기, 그 밖은 뛰기
    - gait_speed [0, s_walk, s_run] (× herb_speed): 정지는 0, 0 < s_walk ≤ s_run
    - gait_eat [e_stop, e_walk, e_run] ≥ 0: `_eat` 의 want 에 곱하는 섭식 배수
    - c_rest, c_move ≥ 0: drain_mult[g] = c_rest + c_move·gait_speed[g]² (스텝 대사 = energy_drain × drain_mult)
    - net_energy_reward: true 면 에너지 보상이 순변화 e_new − e_prev, false 면 v1 획득량 (#4)
    """
    def num(key, x):
        if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) \
                or not math.isfinite(x):
            raise ValueError(f"features.speed.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
        return float(x)

    def vec(key, n):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != n:
            raise ValueError(f"features.speed.{key} 는 값 {n}개 목록이어야 한다. 받은 값: {x!r}")
        return tuple(num(key, v) for v in x)

    t_walk, t_run = vec("thresholds", 2)
    speed = vec("gait_speed", 3)
    eat = vec("gait_eat", 3)
    c_rest, c_move = num("c_rest", p["c_rest"]), num("c_move", p["c_move"])
    net = p["net_energy_reward"]
    if not 0.0 <= t_walk <= t_run <= 1.0:
        raise ValueError(f"features.speed.thresholds 는 0 ≤ 걷기 ≤ 뛰기 ≤ 1 이어야 한다. 받은 값: {[t_walk, t_run]}")
    if speed[0] != 0.0 or not 0.0 < speed[1] <= speed[2]:
        raise ValueError(f"features.speed.gait_speed 는 [0, 걷기, 뛰기], 0 < 걷기 ≤ 뛰기 여야 한다(정지는 속력 0). "
                         f"받은 값: {list(speed)}")
    if min(eat) < 0.0:
        raise ValueError(f"features.speed.gait_eat 는 0 이상이어야 한다. 받은 값: {list(eat)}")
    if c_rest < 0.0 or c_move < 0.0:
        raise ValueError(f"features.speed.c_rest·c_move 는 0 이상이어야 한다. 받은 값: {c_rest}, {c_move}")
    if not isinstance(net, bool):
        raise ValueError(f"features.speed.net_energy_reward 는 true/false 여야 한다. 받은 값: {net!r}")
    sp = np.asarray(speed, dtype=np.float64)
    return dict(thresholds=(t_walk, t_run), speed=sp, eat=np.asarray(eat, dtype=np.float64),
                c_rest=c_rest, c_move=c_move, drain_mult=c_rest + c_move * sp * sp, net_energy_reward=net)


def _food_v_params(p: dict) -> dict:
    """food_v 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    alpha ≥ 0, 0 ≤ floor ≤ 1, 반감기는 하나 이상의 양수(스텝), floor ≤ init_frac[0] ≤ init_frac[1] ≤ 1.
    alpha = 0 이면 훼손이 없어 V 가 cap0 로 돌아가기만 한다.
    """
    def num(key, x):
        if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) \
                or not math.isfinite(x):
            raise ValueError(f"features.food_v.{key} 는 유한한 숫자여야 한다. 받은 값: {x!r}")
        return float(x)

    alpha, floor = num("alpha", p["alpha"]), num("floor", p["floor"])
    hl, fr = p["recovery_half_lives"], p["init_frac"]
    if not isinstance(hl, (list, tuple)) or not hl:
        raise ValueError(f"features.food_v.recovery_half_lives 는 반감기(스텝) 목록이어야 한다. 받은 값: {hl!r}")
    if not isinstance(fr, (list, tuple)) or len(fr) != 2:
        raise ValueError(f"features.food_v.init_frac 는 [하, 상] 두 값이어야 한다. 받은 값: {fr!r}")
    half_lives = tuple(num("recovery_half_lives", h) for h in hl)
    lo, hi = (num("init_frac", x) for x in fr)
    if alpha < 0.0:
        raise ValueError(f"features.food_v.alpha 는 0 이상이어야 한다. 받은 값: {alpha}")
    if not 0.0 <= floor <= 1.0:
        raise ValueError(f"features.food_v.floor 는 [0, 1] 의 cap0 비율이어야 한다. 받은 값: {floor}")
    if min(half_lives) <= 0.0:
        raise ValueError(f"features.food_v.recovery_half_lives 는 양수여야 한다. 받은 값: {list(half_lives)}")
    if not floor <= lo <= hi <= 1.0:
        raise ValueError(f"features.food_v.init_frac 는 floor({floor}) ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    return dict(alpha=alpha, floor=floor, half_lives=half_lives, init_frac=(lo, hi))


def _daynight_params(p: dict, f: Features) -> dict:
    """daynight 계수(yaml 블록, 키는 `features.PARAM_KEYS`)의 값 범위를 검사한다. 기본값은 없다.

    - periods: 하루 길이 T(스텝) 목록, 하나 이상의 양의 짝수 정수(낮·밤이 T/2 씩, 계획서 4.9.2 {600, 900, 1800})
    - twilight ∈ (0, 0.25]: 전환 앞뒤 박명 폭(T 비율). twilight·T 는 정수 스텝이어야 한다(구간 문턱이 비트 단위로 같게)
    - detect_night·eat_night·rest_night ∈ [0, 1]: 어둠 d 에서 (1 − x·d) 를 곱한다. 0 이면 그 효과가 없다
    - fixed_day_frac ∈ [0, 1]: reset 마다 이 확률로 낮 고정 세계(d = 0, 관측은 중립값 1·1)
    - transition_norm ≥ max(periods)/2: to_transition = 남은 스텝 / transition_norm (계약 900, 계획서 4.2)
    - start_induce ∈ [0, 1]: 시작 상태 유도 비율(0 = 끔). `_daynight_reset`·`_respawn` docstring
    - rest_cover_only (bool): true 면 휴식 할인을 결정 때 은신처 안에서 멈춘 개체만 받는다(v2.4b). false = v2.4
    speed 를 함께 켜야 한다(휴식 대사는 보행 상태의 정지 대사에 곱하고, 통계가 보행을 센다).
    """
    if not f.enabled("speed"):
        raise ValueError("features.daynight 는 speed 를 함께 켜야 한다(v2.4 는 v2.1 위의 버전이다)")
    per = p["periods"]
    if not isinstance(per, (list, tuple)) or not per:
        raise ValueError(f"features.daynight.periods 는 하루 길이(스텝) 목록이어야 한다. 받은 값: {per!r}")
    periods = []
    for x in per:
        if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x <= 0 or x % 2:
            raise ValueError(f"features.daynight.periods 는 양의 짝수 정수여야 한다. 받은 값: {list(per)}")
        periods.append(int(x))
    tw = _num("daynight", "twilight", p["twilight"])
    if not 0.0 < tw <= 0.25:
        raise ValueError(f"features.daynight.twilight 는 (0, 0.25] 의 T 비율이어야 한다. 받은 값: {tw}")
    tw_steps = []
    for T in periods:
        k = tw * T
        if abs(k - round(k)) > 1e-9 or round(k) < 1:
            raise ValueError(f"features.daynight.twilight·T 는 1 이상의 정수 스텝이어야 한다. T={T}: {k}")
        tw_steps.append(int(round(k)))
    mult = {}
    for key in ("detect_night", "eat_night", "rest_night", "fixed_day_frac", "start_induce"):
        x = _num("daynight", key, p[key])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.daynight.{key} 는 [0, 1] 이어야 한다. 받은 값: {x}")
        mult[key] = x
    rco = p["rest_cover_only"]
    if not isinstance(rco, bool):
        raise ValueError(f"features.daynight.rest_cover_only 는 true/false 여야 한다. 받은 값: {rco!r}")
    norm = _num("daynight", "transition_norm", p["transition_norm"])
    if norm < max(periods) / 2:
        raise ValueError(f"features.daynight.transition_norm 은 가장 긴 상 길이 {max(periods) // 2} 이상이어야 한다. "
                         f"받은 값: {norm}")
    return dict(periods=tuple(periods), tw_steps=tuple(tw_steps), transition_norm=norm, rest_cover_only=rco, **mult)


def _pred_sleep_params(p: dict, f: Features) -> dict:
    """pred_sleep 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다.

    - nocturnal_frac = [하, 상], 0 ≤ 하 ≤ 상 ≤ 1: reset 마다 야행성 비율 q ~ U[하, 상]
    - sleep_dark ∈ (0, 1]: 주행성 포식자가 자는 어둠 문턱(d ≥ sleep_dark)
    - twilight_slow (bool): 깨어 있는 주행성 포식자 속력 × (1 − d)
    daynight 를 함께 켜야 한다(어둠 d 가 거기 있다).
    """
    if not f.enabled("daynight"):
        raise ValueError("features.pred_sleep 은 daynight 를 함께 켜야 한다(어둠 d 가 daynight 에 있다)")
    fr = p["nocturnal_frac"]
    if not isinstance(fr, (list, tuple)) or len(fr) != 2:
        raise ValueError(f"features.pred_sleep.nocturnal_frac 는 [하, 상] 두 값이어야 한다. 받은 값: {fr!r}")
    lo, hi = (_num("pred_sleep", "nocturnal_frac", x) for x in fr)
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"features.pred_sleep.nocturnal_frac 는 0 ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    sd = _num("pred_sleep", "sleep_dark", p["sleep_dark"])
    if not 0.0 < sd <= 1.0:
        raise ValueError(f"features.pred_sleep.sleep_dark 는 (0, 1] 이어야 한다. 받은 값: {sd}")
    ts = p["twilight_slow"]
    if not isinstance(ts, bool):
        raise ValueError(f"features.pred_sleep.twilight_slow 는 true/false 여야 한다. 받은 값: {ts!r}")
    return dict(nocturnal_frac=(lo, hi), sleep_dark=sd, twilight_slow=ts)


def _threats_params(p: dict, f: Features) -> dict:
    """threats 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (v3 R0, 명세 3절 M3·플레이어형 위협).

    - stalk_frac = [하, 상], 0 ≤ 하 ≤ 상 ≤ 1: reset 마다 p_stalk ~ U[하, 상], 포식자마다 확률 p_stalk 로 잠행-돌진형
    - stalk_dist > 0: 잠행형이 돌진을 시작하는 표적 체감 거리(M1·은신 배수가 든 거리)
    - stalk_speed·pounce_speed·exhaust_speed ≥ 0 (× herb_speed), pounce_steps ≥ 1, exhaust_steps ≥ 0 (정수 스텝)
    - player_frac ∈ [0, 1]: 플레이어형 위협이 있는 세계 비율
    - player_speeds = [배회, 잠행, 돌진] ≥ 0 (× herb_speed), player_mode_steps = [하, 상] 정수 1 ≤ 하 ≤ 상
    - player_stalk_p ∈ [0, 1], player_charge_dist > 0, player_charge_steps ≥ 1, player_rest_steps ≥ 0 (정수)
    - player_catch_r > 0, player_cooldown ≥ 0 (정수 스텝)
    - 선택 키 eat_in_place (bool, 없으면 false — features.OPTIONAL_KEYS, 10-15): 늑대가 잡은 뒤 쿨다운 동안 제자리에서 먹나(모듈
      docstring 'R3 세계' (j)). 켜면 v1 키 pred_eat_cd 가 0 이상의 정수여야 한다(World.__init__ 이 검사한다)
    daynight 를 함께 켜야 한다(v3 는 v2.4s 위의 버전이고, 플레이어는 낮밤과 무관하게 움직이는 위협이다).
    """
    if not f.enabled("daynight"):
        raise ValueError("features.threats 는 daynight 를 함께 켜야 한다(v3 는 v2.4s 위의 버전이다)")
    p = with_optional("threats", p)

    def integer(key, x, lo):
        if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x < lo:
            raise ValueError(f"features.threats.{key} 는 {lo} 이상의 정수(스텝)여야 한다. 받은 값: {x!r}")
        return int(x)

    def pair(key, n):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != n:
            raise ValueError(f"features.threats.{key} 는 값 {n}개 목록이어야 한다. 받은 값: {x!r}")
        return x

    lo, hi = (_num("threats", "stalk_frac", x) for x in pair("stalk_frac", 2))
    if not 0.0 <= lo <= hi <= 1.0:
        raise ValueError(f"features.threats.stalk_frac 는 0 ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {[lo, hi]}")
    out = dict(stalk_frac=(lo, hi))
    for key in ("stalk_speed", "pounce_speed", "exhaust_speed"):
        x = _num("threats", key, p[key])
        if x < 0.0:
            raise ValueError(f"features.threats.{key} 는 0 이상이어야 한다. 받은 값: {x}")
        out[key] = x
    for key in ("stalk_dist", "player_charge_dist", "player_catch_r"):
        x = _num("threats", key, p[key])
        if x <= 0.0:
            raise ValueError(f"features.threats.{key} 는 양수여야 한다. 받은 값: {x}")
        out[key] = x
    for key in ("player_frac", "player_stalk_p"):
        x = _num("threats", key, p[key])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.threats.{key} 는 [0, 1] 이어야 한다. 받은 값: {x}")
        out[key] = x
    out["pounce_steps"] = integer("pounce_steps", p["pounce_steps"], 1)
    out["exhaust_steps"] = integer("exhaust_steps", p["exhaust_steps"], 0)
    out["player_charge_steps"] = integer("player_charge_steps", p["player_charge_steps"], 1)
    out["player_rest_steps"] = integer("player_rest_steps", p["player_rest_steps"], 0)
    out["player_cooldown"] = integer("player_cooldown", p["player_cooldown"], 0)
    sp = tuple(_num("threats", "player_speeds", x) for x in pair("player_speeds", 3))
    if min(sp) < 0.0:
        raise ValueError(f"features.threats.player_speeds 는 0 이상이어야 한다. 받은 값: {list(sp)}")
    out["player_speeds"] = sp
    ms = tuple(integer("player_mode_steps", x, 1) for x in pair("player_mode_steps", 2))
    if ms[0] > ms[1]:
        raise ValueError(f"features.threats.player_mode_steps 는 [하, 상], 하 ≤ 상 이어야 한다. 받은 값: {list(ms)}")
    out["player_mode_steps"] = ms
    if not isinstance(p["eat_in_place"], bool):
        raise ValueError(f"features.threats.eat_in_place 는 true/false 여야 한다. 받은 값: {p['eat_in_place']!r}")
    out["eat_in_place"] = p["eat_in_place"]
    return out


def _stare_params(p: dict, f: Features) -> dict:
    """stare_down 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (v3 R2 M7, 명세 2-4).

    - target_lock (bool): 잠행 위협이 표적을 잠그나. false = '지난 스텝 표적' 기록만 하고 표적 선택은 그대로다
    - spot_r ≥ 0: 노려보기가 통하는 실거리. 0 이면 노려보기 블록을 건너뛴다(비교하지 않는다 — 같은 좌표의 두 개체에서 d ≤ 0 이
      참이 되는 일을 막는다). spot_r 0 이고 target_lock false 면 끈 세계와 비트 동일이다
    - 0 < spot_cos ≤ 1: 눈맞춤 각의 cos, spot_steps ≥ 1 (정수): 이어서 노려봐야 하는 스텝
    - balk_steps·spotted_steps ≥ 0 (정수), balk_speed·spotted_charge_speed ≥ 0 (× herb_speed)
    repertoire·threats 를 함께 켜야 한다(노려보기는 개체 행동 FREEZE 와 잠행 위협 상태 기계를 쓴다).
    """
    if not f.enabled("repertoire") or not f.enabled("threats"):
        raise ValueError("features.stare_down 은 repertoire·threats 를 함께 켜야 한다(노려보기는 FREEZE 행동과 잠행 위협을 쓴다)")
    if not isinstance(p["target_lock"], bool):
        raise ValueError(f"features.stare_down.target_lock 은 true/false 여야 한다. 받은 값: {p['target_lock']!r}")
    out = dict(target_lock=p["target_lock"])
    x = _num("stare_down", "spot_r", p["spot_r"])
    if x < 0.0:
        raise ValueError(f"features.stare_down.spot_r 는 0 이상이어야 한다. 받은 값: {x}")
    out["spot_r"] = x
    x = _num("stare_down", "spot_cos", p["spot_cos"])
    if not 0.0 < x <= 1.0:
        raise ValueError(f"features.stare_down.spot_cos 는 (0, 1] 이어야 한다. 받은 값: {x}")
    out["spot_cos"] = x
    for key, lo in (("spot_steps", 1), ("balk_steps", 0), ("spotted_steps", 0)):
        v = p[key]
        if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < lo:
            raise ValueError(f"features.stare_down.{key} 는 {lo} 이상의 정수(스텝)여야 한다. 받은 값: {v!r}")
        out[key] = int(v)
    for key in ("balk_speed", "spotted_charge_speed"):
        x = _num("stare_down", key, p[key])
        if x < 0.0:
            raise ValueError(f"features.stare_down.{key} 는 0 이상이어야 한다. 받은 값: {x}")
        out[key] = x
    return out


def _alarm_params(p: dict, f: Features) -> dict:
    """alarm 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (v3 R2 M8, 명세 3-5).

    - alarm_r ≥ 0: 들리는 실거리. alarm_steps ≥ 1, max_hop ≥ 0(≤ 254 — C++ uint8 의 255 는 '없음'), relay_window ≥ 0 (정수)
    - 0 < hop_gain ≤ 1, 0 ≤ event_alarm ≤ 1, on_catch (bool)
    반환에 gain(홉별 세기 표, `repertoire.alarm_gain`)과 active(alarm_r > 0 이거나 on_catch — 아니면 중립이라 블록 전체를 건너뛴다)
    를 더한다. repertoire 를 함께 켜야 한다(경보는 행동 전환의 부산물이다). 관측 칸은 obs_extra 가 true 일 때만 붙는다.
    """
    if not f.enabled("repertoire"):
        raise ValueError("features.alarm 은 repertoire 를 함께 켜야 한다(경보는 FLEE·FREEZE·HIDE 전환의 부산물이다)")
    out = {}
    x = _num("alarm", "alarm_r", p["alarm_r"])
    if x < 0.0:
        raise ValueError(f"features.alarm.alarm_r 는 0 이상이어야 한다. 받은 값: {x}")
    out["alarm_r"] = x
    for key, lo, hi in (("alarm_steps", 1, None), ("max_hop", 0, rep.AL_NONE - 1), ("relay_window", 0, None)):
        v = p[key]
        if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < lo or (hi is not None and v > hi):
            raise ValueError(f"features.alarm.{key} 는 {lo} 이상의 정수여야 한다"
                             + (f"(≤ {hi})" if hi is not None else "") + f". 받은 값: {v!r}")
        out[key] = int(v)
    x = _num("alarm", "hop_gain", p["hop_gain"])
    if not 0.0 < x <= 1.0:
        raise ValueError(f"features.alarm.hop_gain 은 (0, 1] 이어야 한다. 받은 값: {x}")
    out["hop_gain"] = x
    x = _num("alarm", "event_alarm", p["event_alarm"])
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"features.alarm.event_alarm 은 [0, 1] 이어야 한다. 받은 값: {x}")
    out["event_alarm"] = x
    if not isinstance(p["on_catch"], bool):
        raise ValueError(f"features.alarm.on_catch 는 true/false 여야 한다. 받은 값: {p['on_catch']!r}")
    out["on_catch"] = p["on_catch"]
    out["gain"] = rep.alarm_gain(out["hop_gain"], out["max_hop"])
    out["active"] = out["alarm_r"] > 0.0 or out["on_catch"]
    return out


def _fov_cos(deg: float, base_deg: float, base_cos: float) -> float:
    """시야각(도) → 판정 문턱 cos(시야각/2). 기본 시야각과 같으면 v1 상수(cfg.fov_cos) 그대로, 360 이면 −inf(각도 판정 없음 —
    cos(180°) = −1 과의 비교는 반올림으로 정반대 방향을 놓칠 수 있다, `_vigil_params` 와 같은 규칙)."""
    if deg == float(base_deg):
        return base_cos
    return -math.inf if deg >= 360.0 else math.cos(math.radians(deg) * 0.5)


def _rz_need_repertoire(name: str, f: Features) -> None:
    if not f.enabled("repertoire"):
        raise ValueError(f"features.{name} 는 repertoire 를 함께 켜야 한다(v3 현실성 1단계는 행동 레퍼토리 세계 위의 규칙이다)")


def _rz_vision_params(p: dict, f: Features, cfg) -> dict:
    """realism_vision 계수 (모듈 docstring (a)). threat_fov_deg·kin_fov_deg ∈ [fov_deg(v1 120), 360]. 반환에 문턱 cos 를 더한다
    (기본 시야각이면 cfg.fov_cos 그대로라 그 판정은 비트 단위로 같다). repertoire 를 함께 켜야 한다."""
    _rz_need_repertoire("realism_vision", f)
    out = {}
    for key in ("threat_fov_deg", "kin_fov_deg"):
        x = _num("realism_vision", key, p[key])
        if not float(cfg.fov_deg) <= x <= 360.0:
            raise ValueError(f"features.realism_vision.{key} 는 기본 시야각 {cfg.fov_deg} 이상 360 이하여야 한다(좁히지 않는다). "
                             f"받은 값: {x}")
        out[key] = x
    out["threat_cos"] = _fov_cos(out["threat_fov_deg"], cfg.fov_deg, cfg.fov_cos)
    out["kin_cos"] = _fov_cos(out["kin_fov_deg"], cfg.fov_deg, cfg.fov_cos)
    return out


def _rz_hearing_params(p: dict, f: Features) -> dict:
    """realism_hearing 계수 (모듈 docstring (b)). 0 ≤ r_quiet ≤ r_loud, 0 < s_silent ≤ s_quiet < s_loud (× herb_speed),
    cap_to_sight·roam_quiet (bool). repertoire 를 함께 켜야 한다(위협의 지난 이동 pred_vel 과 사슴 행동별 탐지 반경을 쓴다)."""
    _rz_need_repertoire("realism_hearing", f)
    out = {k: _num("realism_hearing", k, p[k]) for k in ("r_quiet", "r_loud", "s_silent", "s_quiet", "s_loud")}
    if not 0.0 <= out["r_quiet"] <= out["r_loud"]:
        raise ValueError(f"features.realism_hearing 는 0 ≤ r_quiet ≤ r_loud 여야 한다. 받은 값: {out['r_quiet']}, {out['r_loud']}")
    if not 0.0 < out["s_silent"] <= out["s_quiet"] < out["s_loud"]:
        raise ValueError("features.realism_hearing 는 0 < s_silent ≤ s_quiet < s_loud 여야 한다. 받은 값: "
                         f"{out['s_silent']}, {out['s_quiet']}, {out['s_loud']}")
    for key in ("cap_to_sight", "roam_quiet"):
        if not isinstance(p[key], bool):
            raise ValueError(f"features.realism_hearing.{key} 는 true/false 여야 한다. 받은 값: {p[key]!r}")
        out[key] = p[key]
    return out


def hearing_radius(zh: dict, s: np.ndarray, running: np.ndarray | None = None) -> np.ndarray:
    """위협의 지난 스텝 속력 s(× herb_speed)·걸음새(running = 전력 걸음, 훅 `World.pred_running`)의 소리 반경 R
    (모듈 docstring (b)). roam_quiet 면 전력 걸음이 아닌 위협의 속력을 s_quiet 에서 자른다(running 이 None 이면 모두 전력 걸음).
    C++ 꼴:
      float S2 = (bRoamQuiet && !bRunning) ? FMath::Min(S, SQuiet) : S;
      float T = FMath::Clamp((S2 - SQuiet) / (SLoud - SQuiet), 0, 1);  R = S2 < SSilent ? 0 : RQuiet + (RLoud - RQuiet) * T;"""
    s = np.asarray(s, dtype=np.float64)
    if zh["roam_quiet"] and running is not None:
        s = np.where(np.asarray(running, dtype=bool), s, np.minimum(s, zh["s_quiet"]))
    t = np.clip((s - zh["s_quiet"]) / (zh["s_loud"] - zh["s_quiet"]), 0.0, 1.0)
    return np.where(s < zh["s_silent"], 0.0, zh["r_quiet"] + (zh["r_loud"] - zh["r_quiet"]) * t)


def _rz_shelter_params(p: dict, f: Features) -> dict:
    """realism_shelter 계수 (모듈 docstring (c)·(c′)). untargetable·player_too (bool), 선택 키 block_predators (bool, 없으면 false —
    features.OPTIONAL_KEYS). repertoire 를 함께 켜야 한다(v3 포식자 스텝의 표적·포획 판정·이동에 얹는다)."""
    _rz_need_repertoire("realism_shelter", f)
    p = with_optional("realism_shelter", p)
    out = {}
    for key in ("untargetable", "player_too", "block_predators"):
        if not isinstance(p[key], bool):
            raise ValueError(f"features.realism_shelter.{key} 는 true/false 여야 한다. 받은 값: {p[key]!r}")
        out[key] = p[key]
    # (c″) 늑대 몸 여유(선택 키, 10-17): 0 이상 유한한 수. 막는 위협이 없으면(block_predators false) 뜻이 없어 0 만 받는다
    m = p["wolf_margin"]
    if isinstance(m, bool) or not isinstance(m, (int, float)) or not math.isfinite(float(m)) or float(m) < 0.0:
        raise ValueError(f"features.realism_shelter.wolf_margin 은 0 이상 유한한 수(단위)여야 한다. 받은 값: {m!r}")
    if float(m) > 0.0 and not out["block_predators"]:
        raise ValueError("features.realism_shelter.wolf_margin 은 block_predators true 일 때만 0 보다 클 수 있다(늑대 몸 여유는 진입 금지의 "
                         f"반지름이다). 받은 값: {m!r}")
    out["wolf_margin"] = float(m)
    return out


def _rz_cover_food_params(p: dict, f: Features) -> dict:
    """realism_cover_food 계수 (모듈 docstring (e)·(e′)). 선택 키 frac_range 가 null(없으면 null — features.OPTIONAL_KEYS)이면
    cap_frac ∈ [0, 1] = 은신처 셀 용량 배수, regen_frac ∈ [0, 1] = 은신처 셀 재생률 / 밖 재생률(v1 은 cfg.food_cover_regen_mult 0.3).
    frac_range = [하, 상] (0 ≤ 하 ≤ 상 ≤ 1)이면 세계마다 하나를 뽑아 둘에 함께 쓰고, cap_frac·regen_frac 는 null 이어야 한다(값이 둘로
    적혀 있으면 어느 쪽이 쓰이는지 헷갈린다). repertoire 를 함께 켜야 한다(v3 현실성 단계의 규칙이다)."""
    _rz_need_repertoire("realism_cover_food", f)
    p = with_optional("realism_cover_food", p)
    out = {"frac_range": None}
    fr = p["frac_range"]
    if fr is not None:
        if not isinstance(fr, (list, tuple)) or len(fr) != 2:
            raise ValueError(f"features.realism_cover_food.frac_range 는 [하, 상] 두 수이거나 null 이다. 받은 값: {fr!r}")
        lo, hi = (_num("realism_cover_food", "frac_range", x) for x in fr)
        if not 0.0 <= lo <= hi <= 1.0:
            raise ValueError(f"features.realism_cover_food.frac_range 는 0 ≤ 하 ≤ 상 ≤ 1 이어야 한다. 받은 값: {fr!r}")
        if p["cap_frac"] is not None or p["regen_frac"] is not None:
            raise ValueError("features.realism_cover_food 에 frac_range 를 쓰면 cap_frac·regen_frac 는 null 로 둔다(세계마다 뽑은 배수 "
                             f"하나가 둘을 정한다). 받은 값: cap_frac {p['cap_frac']!r}, regen_frac {p['regen_frac']!r}")
        out.update(frac_range=(lo, hi), cap_frac=None, regen_frac=None)
        return out
    for key in ("cap_frac", "regen_frac"):
        x = _num("realism_cover_food", key, p[key])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.realism_cover_food.{key} 는 [0, 1] 이어야 한다(밖보다 늘리지 않는다). 받은 값: {x}")
        out[key] = x
    return out


def _rz_chase_params(p: dict, f: Features) -> dict:
    """realism_chase 계수 (모듈 docstring 'R3 세계' (f)). lost_steps ≥ 0 정수(스텝), stalk_phase·player_too (bool). repertoire 를 함께
    켜야 하고 stare_down 과는 함께 켜지 않는다(노려보기의 잠금 M7a 도 표적을 고정해 두 규칙이 같은 표적을 두고 다툰다)."""
    _rz_need_repertoire("realism_chase", f)
    if f.enabled("stare_down"):
        raise ValueError("features.realism_chase 는 stare_down 과 함께 켜지 않는다(둘 다 위협의 표적을 고정한다 — 노려보기는 10-13 사람 "
                         "결정으로 빠졌다)")
    v = p["lost_steps"]
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 0:
        raise ValueError(f"features.realism_chase.lost_steps 는 0 이상의 정수(스텝)여야 한다. 받은 값: {v!r}")
    out = {"lost_steps": int(v)}
    for key in ("stalk_phase", "player_too"):
        if not isinstance(p[key], bool):
            raise ValueError(f"features.realism_chase.{key} 는 true/false 여야 한다. 받은 값: {p[key]!r}")
        out[key] = p[key]
    return out


def _rz_terrain_params(p: dict, f: Features) -> dict:
    """realism_terrain 계수 (모듈 docstring 'R3 세계' (h)). snow_frac·rough_frac = [하, 상] (0 ≤ 하 ≤ 상 ≤ 1), zero_p = [눈, 거친 땅]
    각 [0, 1], patch_r = [하, 상] (0 < 하 ≤ 상), max_patches ≥ 0 정수, mult_herb·mult_pred·mult_player = [보통, 눈, 거친 땅] 세 수 —
    각 (0, 1](느려지기만 한다)이고 보통은 1(지금 세계의 속력이 보통 땅이다). repertoire 를 함께 켜야 한다(v3 포식자 스텝에만 넣는다)."""
    _rz_need_repertoire("realism_terrain", f)

    def pair(key, lo_ok, ordered=True):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != 2:
            raise ValueError(f"features.realism_terrain.{key} 는 두 수 [하, 상] 이다. 받은 값: {x!r}")
        a, b = (_num("realism_terrain", key, v) for v in x)
        if not (lo_ok(a) and lo_ok(b)) or (ordered and a > b):
            raise ValueError(f"features.realism_terrain.{key} 의 범위가 틀렸다. 받은 값: {x!r}")
        return a, b

    out = {"snow_frac": pair("snow_frac", lambda v: 0.0 <= v <= 1.0),
           "rough_frac": pair("rough_frac", lambda v: 0.0 <= v <= 1.0),
           "zero_p": pair("zero_p", lambda v: 0.0 <= v <= 1.0, ordered=False),
           "patch_r": pair("patch_r", lambda v: v > 0.0)}
    v = p["max_patches"]
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 0:
        raise ValueError(f"features.realism_terrain.max_patches 는 0 이상의 정수다. 받은 값: {v!r}")
    out["max_patches"] = int(v)
    for key in ("mult_herb", "mult_pred", "mult_player"):
        x = p[key]
        if not isinstance(x, (list, tuple)) or len(x) != len(TERRAIN_NAMES):
            raise ValueError(f"features.realism_terrain.{key} 는 [보통, 눈, 거친 땅] 세 수다. 받은 값: {x!r}")
        m = np.array([_num("realism_terrain", key, v) for v in x], dtype=np.float64)
        if m[TERRAIN_NORMAL] != 1.0 or not ((m > 0.0) & (m <= 1.0)).all():
            raise ValueError(f"features.realism_terrain.{key} 는 보통 1 이고 모두 (0, 1] 이어야 한다(땅은 느리게만 한다). 받은 값: {x!r}")
        out[key] = m
    return out


def _rz_night_params(p: dict, f: Features, ps: dict | None) -> dict:
    """realism_night 계수 (모듈 docstring (d)). settle_r ≥ 0, sleep_dark < hunt_dark ≤ 1, 0 ≤ night_floor ≤ 1 − sleep_dark (해 지는
    순간의 속력 1 − sleep_dark 보다 크면 해 질 녘·새벽의 (1 − d) 감속까지 덮고, 해 질 때 속력이 다시 오른다), 0 ≤ spread ≤ 1 (박명 폭
    τ 비율), ramp_steps ≥ 0 정수(0 = 눕기·깨기가 한 업데이트에 끝남). pred_sleep·repertoire 를 함께 켜야 한다(pred_sleep 의 잠을 바꾸는
    규칙이고, 사냥 중 판정은 v3 포식자 스텝이 남긴다)."""
    _rz_need_repertoire("realism_night", f)
    if ps is None:
        raise ValueError("features.realism_night 는 pred_sleep 을 함께 켜야 한다(주행성 늑대의 밤잠을 바꾸는 규칙이다)")
    out = {}
    x = _num("realism_night", "settle_r", p["settle_r"])
    if x < 0.0:
        raise ValueError(f"features.realism_night.settle_r 는 0 이상이어야 한다. 받은 값: {x}")
    out["settle_r"] = x
    x = _num("realism_night", "hunt_dark", p["hunt_dark"])
    if not ps["sleep_dark"] < x <= 1.0:
        raise ValueError(f"features.realism_night.hunt_dark 는 pred_sleep.sleep_dark({ps['sleep_dark']}) 초과 1 이하여야 한다. "
                         f"받은 값: {x}")
    out["hunt_dark"] = x
    for key in ("night_floor", "spread"):
        x = _num("realism_night", key, p[key])
        if not 0.0 <= x <= 1.0:
            raise ValueError(f"features.realism_night.{key} 는 [0, 1] 이어야 한다. 받은 값: {x}")
        out[key] = x
    if out["night_floor"] > 1.0 - ps["sleep_dark"]:
        raise ValueError(f"features.realism_night.night_floor 는 1 − pred_sleep.sleep_dark({1.0 - ps['sleep_dark']}) 이하여야 한다"
                         f"(해 질 녘·새벽 감속은 pred_sleep 그대로 두고 해 진 뒤에만 하한을 건다). 받은 값: {out['night_floor']}")
    v = p["ramp_steps"]
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 0:
        raise ValueError(f"features.realism_night.ramp_steps 는 0 이상의 정수(스텝)여야 한다. 받은 값: {v!r}")
    out["ramp_steps"] = int(v)
    return out


# 통합 무대 (q) head_layout 'golden' 의 순번 각(rad, C++ AEcoCreatureIntegrationSpawner 의 2.399963 그대로)과 늑대 순번 밀기
# 야생 (w3) 도주 반사 덮기 wf_mode (모듈 docstring '야생 1단계'). C++ kKeepNone·kKeepAlert·kKeepPanic·kKeepShelter 와 같은 번호
WF_NONE, WF_ALERT, WF_PANIC, WF_SHELTER = 0, 1, 2, 3
WF_MODE_NAMES = ("none", "alert", "panic", "shelter")
IST_GOLDEN_ANGLE = 2.399963
IST_WOLF_HEAD_OFFSET = 2
# 통합 무대 (p) 늑대 모서리 순서(C++ PlanStage Corners)와 무작위 자리 시도 수, 사슴 시도 수 max(IST_DEER_TRIES_MIN, IST_DEER_TRIES_PER × N)
IST_CORNERS = ((1.0, 1.0), (-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0))
IST_WOLF_TRIES = 400
IST_DEER_TRIES_MIN, IST_DEER_TRIES_PER = 64, 60
# 통합 무대 (n) quad 은신처: 원마다 시도 수, 반경 줄이는 시도 번호, 돌리는 각(도), 무대 안 여유·원 사이 간격에 더하는 값(단위 — C++ 200·400 cm)
IST_COVER_TRIES = 24
IST_COVER_SHRINK_AT = 12
IST_COVER_TURN_DEG = 15.0
IST_COVER_MARGIN, IST_COVER_GAP = 1.0, 2.0


def _ist_params(p: dict, f: Features) -> dict:
    """integrated_stage 계수(yaml 블록, 키는 `features.PARAM_KEYS`)를 검사한다. 기본값은 없다 (모듈 docstring '통합 무대').

    - respawn (bool): false 면 부활 없음 (k). alarm·stare_down 과 함께 켤 수 없다(죽은 개체를 빼는 규칙이 없다)
    - ema_den: null 또는 1 이상의 정수 (l)
    - day_offset: null 또는 0 이상의 정수(스텝) (m). daynight 를 함께 켜야 한다(repertoire 가 이미 요구한다)
    - cover_layout: null 또는 'quad' (n). quad 면 cover_count 1 이상의 정수, cover_r_frac 양수(아니면 둘 다 null 이어도 된다)
    - wolf_kinds: null 또는 'alternate' (o)
    - start_layout: null 또는 'stage' (p). stage 면 wolf_corner_frac ∈ [0, 0.5], wolf_gap·deer_wolf_gap·deer_margin·deer_spacing ≥ 0 (단위)
    - head_layout: null 또는 'golden' (q)
    repertoire·threats 를 함께 켜야 한다(언리얼 통합 v3 모드는 v3 세계이고 늑대 구성이 threats 에 있다).
    """
    if not (f.enabled("repertoire") and f.enabled("threats")):
        raise ValueError("features.integrated_stage 는 repertoire·threats 를 함께 켜야 한다(언리얼 통합 v3 모드는 v3 세계다)")

    def choice(key, allowed):
        x = p[key]
        if x is not None and x not in allowed:
            raise ValueError(f"features.integrated_stage.{key} 는 null 또는 {', '.join(allowed)} 이어야 한다. 받은 값: {x!r}")
        return x

    def integer(key, lo, nullable=True):
        x = p[key]
        if x is None and nullable:
            return None
        if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x < lo:
            raise ValueError(f"features.integrated_stage.{key} 는 {'null 또는 ' if nullable else ''}{lo} 이상의 정수여야 한다. 받은 값: {x!r}")
        return int(x)

    def number(key, lo, hi=math.inf, open_lo=False):
        x = _num("integrated_stage", key, p[key])
        if (x <= lo if open_lo else x < lo) or x > hi:
            raise ValueError(f"features.integrated_stage.{key} 는 {'(' if open_lo else '['}{lo}, {hi}] 이어야 한다. 받은 값: {x}")
        return x

    resp = p["respawn"]
    if not isinstance(resp, bool):
        raise ValueError(f"features.integrated_stage.respawn 은 true/false 여야 한다. 받은 값: {resp!r}")
    if not resp:
        for name in ("alarm", "stare_down"):
            if f.enabled(name):
                raise ValueError(f"features.integrated_stage.respawn false 는 {name} 와 함께 켜지 못한다(죽은 개체를 빼는 규칙을 넣지 않았다)")
    out = dict(respawn=resp, ema_den=integer("ema_den", 1), day_offset=integer("day_offset", 0),
               cover_layout=choice("cover_layout", ("quad",)), wolf_kinds=choice("wolf_kinds", ("alternate",)),
               start_layout=choice("start_layout", ("stage",)), head_layout=choice("head_layout", ("golden",)))
    if out["cover_layout"] is not None:
        out["cover_count"] = integer("cover_count", 1, nullable=False)
        out["cover_r_frac"] = number("cover_r_frac", 0.0, open_lo=True)
    if out["start_layout"] is not None:
        out["wolf_corner_frac"] = number("wolf_corner_frac", 0.0, 0.5)
        for key in ("wolf_gap", "deer_wolf_gap", "deer_margin", "deer_spacing"):
            out[key] = number(key, 0.0)
    return out


def _wild_num(name: str, p: dict, key: str, lo: float, hi: float = math.inf, open_lo: bool = False) -> float:
    x = _num(name, key, p[key])
    if (x <= lo if open_lo else x < lo) or x > hi:
        raise ValueError(f"features.{name}.{key} 는 {'(' if open_lo else '['}{lo}, {hi}] 이어야 한다. 받은 값: {x}")
    return x


def _wild_bool(name: str, p: dict, key: str) -> bool:
    if not isinstance(p[key], bool):
        raise ValueError(f"features.{name}.{key} 는 true/false 여야 한다. 받은 값: {p[key]!r}")
    return p[key]


def _wild_reserve_params(p: dict, f: Features) -> dict:
    """wild_reserve 계수 (모듈 docstring '야생 1단계' (w1)). daynight 를 함께 켜야 한다(reserve_days 를 하루 길이로 스텝에 옮긴다)."""
    if not f.enabled("daynight"):
        raise ValueError("features.wild_reserve 는 daynight 를 함께 켜야 한다(비축 계수가 게임 하루 단위다)")
    n = "wild_reserve"
    return dict(reserve_days=_wild_num(n, p, "reserve_days", 0.0, open_lo=True), init=_wild_num(n, p, "init", 0.0, 1.0),
                refill_e=_wild_num(n, p, "refill_e", 0.0, 1.0), refill_frac=_wild_num(n, p, "refill_frac", 0.0, 1.0),
                weak_e=_wild_num(n, p, "weak_e", 0.0, 1.0), weak_speed=_wild_num(n, p, "weak_speed", 0.0, 1.0))


def _wild_satiation_params(p: dict, f: Features) -> dict:
    """wild_satiation 계수 (모듈 docstring '야생 1단계' (w2)). daynight 와 v3 포식자 스텝(repertoire 또는 threats)을 함께 켜야 한다."""
    if not f.enabled("daynight") or not (f.enabled("repertoire") or f.enabled("threats")):
        raise ValueError("features.wild_satiation 은 daynight 와 repertoire 또는 threats 를 함께 켜야 한다(v3 포식자 스텝, 게임 하루 단위)")
    n = "wild_satiation"
    return dict(sat_days=_wild_num(n, p, "sat_days", 0.0), rest_speed=_wild_num(n, p, "rest_speed", 0.0, 1.0))


def _wild_flight_params(p: dict, f: Features) -> dict:
    """wild_flight 계수 (모듈 docstring '야생 1단계' (w3)). repertoire 를 함께 켜야 한다. 거리는 0 < flight_r ≤ alert_r ≤ safe_r 여야 한다."""
    if not f.enabled("repertoire"):
        raise ValueError("features.wild_flight 는 repertoire 를 함께 켜야 한다(덮기는 행동 실행기 위에서 돈다)")
    n = "wild_flight"
    p = with_optional(n, p)
    out = dict(alert_r=_wild_num(n, p, "alert_r", 0.0, open_lo=True), flight_r=_wild_num(n, p, "flight_r", 0.0, open_lo=True),
               safe_r=_wild_num(n, p, "safe_r", 0.0, open_lo=True), approach=_wild_num(n, p, "approach", 0.0, 1.0),
               alert_w=_wild_num(n, p, "alert_w", 0.0), rest_alert=_wild_bool(n, p, "rest_alert"),
               shelter_cos=_wild_num(n, p, "shelter_cos", -1.0, 1.0), shelter_r=_wild_num(n, p, "shelter_r", 0.0),
               crouch=_wild_bool(n, p, "crouch"), wall_margin=_wild_num(n, p, "wall_margin", 0.0),
               hold_awake=_wild_bool(n, p, "hold_awake"), edge_r=_wild_num(n, p, "edge_r", 0.0))
    if not out["flight_r"] <= out["alert_r"] <= out["safe_r"]:
        raise ValueError(f"features.wild_flight 는 flight_r ≤ alert_r ≤ safe_r 여야 한다. 받은 값: {out['flight_r']}, "
                         f"{out['alert_r']}, {out['safe_r']}")
    return out


def _wild_pack_params(p: dict, f: Features) -> dict:
    """wild_pack 계수 (모듈 docstring '야생 2단계' 2). threats 를 함께 켜야 한다(늑대 유형·잠행형 상태로 앞장·돕는 늑대를 가른다)."""
    if not f.enabled("threats"):
        raise ValueError("features.wild_pack 은 threats 를 함께 켜야 한다(늑대 유형·잠행형 상태를 쓴다)")
    n = "wild_pack"
    return dict(join_r=_wild_num(n, p, "join_r", 0.0, open_lo=True), lead=_wild_num(n, p, "lead", 0.0),
                door_r=_wild_num(n, p, "door_r", 0.0), door_cos=_wild_num(n, p, "door_cos", -1.0, 1.0),
                wait_r=_wild_num(n, p, "wait_r", 0.0))


def _obstacles_params(p: dict, f: Features) -> dict:
    """obstacles 계수 (모듈 docstring '야생 2단계' 3). v3 포식자 스텝(repertoire 또는 threats)을 함께 켜야 하고, 시야를 가리지 않는 realism_chase·
    stare_down 과는 함께 켜지 않는다. fixed(선택 키)는 [[x, y, r], …] — r > 0, 모두 유한한 수."""
    if not (f.enabled("repertoire") or f.enabled("threats")):
        raise ValueError("features.obstacles 는 repertoire 또는 threats 를 함께 켜야 한다(v3 포식자 스텝이 늑대 이동·표적 보임을 가린다)")
    for other in ("realism_chase", "stare_down"):
        if f.enabled(other):
            raise ValueError(f"features.obstacles 는 {other} 와 함께 켜지 않는다(그 규칙의 시야 판정은 원판을 모른다)")
    n = "obstacles"
    p = with_optional(n, p)

    def rng_pair(key):
        v = p[key]
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ValueError(f"features.obstacles.{key} 는 [하, 상] 이어야 한다. 받은 값: {v!r}")
        lo, hi = _num(n, key, v[0]), _num(n, key, v[1])
        if not 0.0 < lo <= hi:
            raise ValueError(f"features.obstacles.{key} 는 0 < 하 ≤ 상 이어야 한다. 받은 값: {v!r}")
        return lo, hi

    out = dict(tree_per_ha=_wild_num(n, p, "tree_per_ha", 0.0), tree_r=rng_pair("tree_r"),
               rock_per_ha=_wild_num(n, p, "rock_per_ha", 0.0), rock_r=rng_pair("rock_r"),
               body_r=_wild_num(n, p, "body_r", 0.0), block_sight=_wild_bool(n, p, "block_sight"), no_food=_wild_bool(n, p, "no_food"),
               fixed=None)
    if p["fixed"] is not None:
        a = np.asarray(p["fixed"], dtype=np.float64)
        a = a.reshape(-1, len(OBSTACLE_COLUMNS)) if a.size else np.zeros((0, len(OBSTACLE_COLUMNS)))
        if not np.isfinite(a).all() or (a[:, 2] <= 0.0).any():
            raise ValueError("features.obstacles.fixed 는 [[x, y, r], …](유한한 수, r > 0) 이어야 한다")
        out["fixed"] = a
    return out


def obstacle_layout(g: np.random.Generator, size: float, cov_c: np.ndarray, cov_r: np.ndarray, op: dict) -> np.ndarray:
    """세로 장애물 무작위 배치 (모듈 docstring '야생 2단계' 3 의 1)). g = 자기 스트림 part 0. 나무 줄기 round(tree_per_ha × ha) 개, 그다음 바위
    round(rock_per_ha × ha) 개(ha = (S × 2 m)² ÷ 10000). 하나마다 (x, y) ~ U[0, S]², r ~ U[하, 상] 를 뽑고 중심이 은신처 원 안(|c − c_k|² ≤ r_k², 반경
    0 이하는 건너뜀)이거나 무대 벽에서 e = r + OB_EDGE_BODIES·body_r 안(x < e, x > S − e, y 도 같음)이면 다시 뽑는다(OB_TRIES 번, 다 실패하면 건너뜀).
    반환 (K, 3) [x, y, r]."""
    ha = (float(size) * OB_UNIT_M) ** 2 / 10000.0
    out = []
    for per_ha, (lo, hi) in ((op["tree_per_ha"], op["tree_r"]), (op["rock_per_ha"], op["rock_r"])):
        n = int(math.floor(per_ha * ha + 0.5))
        for _ in range(n):
            for _t in range(OB_TRIES):
                c = g.uniform(0.0, size, 2)
                r = float(g.uniform(lo, hi))
                e = r + OB_EDGE_BODIES * float(op["body_r"])
                ok = bool(e <= c[0] <= size - e and e <= c[1] <= size - e)
                for (cx, cy), cr in zip(cov_c, cov_r):
                    if not ok:
                        break
                    if cr > 0.0 and (c[0] - cx) * (c[0] - cx) + (c[1] - cy) * (c[1] - cy) <= cr * cr:
                        ok = False
                        break
                if ok:
                    out.append((float(c[0]), float(c[1]), r))
                    break
    return np.asarray(out, dtype=np.float64).reshape(-1, len(OBSTACLE_COLUMNS))


def obstacle_inside(q: np.ndarray, discs: np.ndarray, body_r: float) -> np.ndarray:
    """위치 q (n, 2) 가 어느 원판(반지름 r + body_r) 안인가(|q − c| < R, 둘레 위는 밖) (n,) bool. C++ EcoThreatV3::InsideAnyObstacle."""
    if not len(discs) or not len(q):
        return np.zeros(len(q), dtype=bool)
    ex = q[:, 0:1] - discs[:, 0][None, :]
    ey = q[:, 1:2] - discs[:, 1][None, :]
    return (np.sqrt(ex * ex + ey * ey) < (discs[:, 2] + body_r)[None, :]).any(1)


def obstacle_slide(p: np.ndarray, q: np.ndarray, discs: np.ndarray, body_r: float,
                   size: float | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """세로 장애물 미끄러짐 (모듈 docstring '야생 2단계' 3 의 2)). p (n, 2) 이동 전(모든 원판 밖), q (n, 2) 가려던 자리 → (새 q, 부딪힘, 물러남) (n,) bool 둘.
    개체마다 OB_PASSES 번: d = q − p, a = d·d 가 0 이면 멈춘다. 원판 k(R = r + body_r)마다 f = p − c, cc = f·f − R², b = f·d. cc < 0(시작점이 원 안)이나
    b ≥ 0(멀어짐)이면 건너뛰고, D = b² − a·cc < 0 이면 안 닿는다. t = (−b − √D) / a ≤ 1 인 가장 작은 t(같으면 앞 번호)의 원 k 에 닿는다:
    h = p + t·d, u = (h − c)/|h − c|(|h − c| ≤ EPS 면 (1, 0)), h ← c + (R + OB_EPS)·u, 남은 이동 m = q − h 의 안쪽 성분 v = min(m·u, 0) 을 빼서
    q ← h + (m − v·u), p ← h. size 를 주면(사슴) 되풀이마다 q 를 [0, size]² 로 자른다. 끝에 q 가 어느 원판 안이면(무대 자르기·겹친 원판) 마지막으로
    닿은 자리 p(size 를 주면 [0, size]² 로 자른 p), 그것도 안이면 처음 자리로 물러난다(물러남 — 벽과 원판 사이 구석에 낀 사슴). 스칼라 식이라 C++ EcoThreatV3::ObstacleSlide 와 같은 순서다(골든 비트 동일).
    C++ 꼴: for pass: … if (Cc < 0 || B >= 0) continue; D = B*B - A*Cc; if (D < 0) continue; T = (-B - sqrt(D)) / A; if (T <= 1 && T < Best) …"""
    q = np.array(q, dtype=np.float64, copy=True)
    hit = np.zeros(len(q), dtype=bool)
    if not len(discs) or not len(q):
        return q, hit, np.zeros(len(q), dtype=bool)
    p0 = np.array(p, dtype=np.float64, copy=True)
    p = p0.copy()
    cx, cy = discs[:, 0][None, :], discs[:, 1][None, :]
    R = (discs[:, 2] + body_r)[None, :]
    act = np.ones(len(q), dtype=bool)
    ar = np.arange(len(q))
    for _ in range(OB_PASSES):
        dx = q[:, 0] - p[:, 0]
        dy = q[:, 1] - p[:, 1]
        a = dx * dx + dy * dy
        act &= a > 0.0
        if not act.any():
            break
        fx = p[:, 0:1] - cx
        fy = p[:, 1:2] - cy
        cc = fx * fx + fy * fy - R * R
        b = fx * dx[:, None] + fy * dy[:, None]
        disc = b * b - a[:, None] * cc
        ok = act[:, None] & (cc >= 0.0) & (b < 0.0) & (disc >= 0.0)
        t = np.full(ok.shape, np.inf)
        t[ok] = (-b[ok] - np.sqrt(disc[ok])) / np.broadcast_to(a[:, None], ok.shape)[ok]
        t = np.where(t <= 1.0, t, np.inf)
        k = t.argmin(1)
        tk = t[ar, k]
        go = np.isfinite(tk)
        act &= go
        if not go.any():
            break
        i = np.flatnonzero(go)
        kk = k[i]
        hx = p[i, 0] + tk[i] * dx[i]
        hy = p[i, 1] + tk[i] * dy[i]
        ccx, ccy = discs[kk, 0], discs[kk, 1]
        ex, ey = hx - ccx, hy - ccy
        e = np.sqrt(ex * ex + ey * ey)
        far = e > EPS
        ux = np.where(far, ex / np.where(far, e, 1.0), 1.0)
        uy = np.where(far, ey / np.where(far, e, 1.0), 0.0)
        rr = (discs[kk, 2] + body_r) + OB_EPS
        hx = ccx + rr * ux
        hy = ccy + rr * uy
        mx, my = q[i, 0] - hx, q[i, 1] - hy
        vn = np.minimum(mx * ux + my * uy, 0.0)
        nx = hx + (mx - vn * ux)
        ny = hy + (my - vn * uy)
        if size is not None:
            nx = np.minimum(np.maximum(nx, 0.0), size)
            ny = np.minimum(np.maximum(ny, 0.0), size)
        q[i, 0], q[i, 1] = nx, ny
        p[i, 0], p[i, 1] = hx, hy
        hit[i] = True
    back = hit & obstacle_inside(q, discs, body_r)
    if back.any():
        lp = p if size is None else np.minimum(np.maximum(p, 0.0), size)
        lp_in = obstacle_inside(lp, discs, body_r)
        q[back] = np.where(lp_in[back][:, None], p0[back], lp[back])
    return q, hit, back


def sight_blocked(a: np.ndarray, b: np.ndarray, discs: np.ndarray) -> np.ndarray:
    """세로 장애물 시선 (모듈 docstring '야생 2단계' 3 의 3)). a (n, 2)·b (m, 2) → (n, m) bool: a_i 와 b_j 를 잇는 선분이 어느 원판을 지나는가 —
    d = b − a, dd = d·d, t = clip(((c − a)·d) / dd, 0, 1)(dd = 0 이면 0), 가장 가까운 점과 중심의 거리² (a + t·d − c)² < r². 발소리는 가리지 않는다.
    C++ 꼴: EcoThreatV3::SightBlocked(Ax, Ay, Bx, By, Discs, Num) — 같은 식, 원판 순서로 하나라도 참이면 참."""
    out = np.zeros((len(a), len(b)), dtype=bool)
    if not len(discs) or not len(a) or not len(b):
        return out
    ax, ay = a[:, 0][:, None, None], a[:, 1][:, None, None]
    dx = b[:, 0][None, :, None] - ax
    dy = b[:, 1][None, :, None] - ay
    dd = dx * dx + dy * dy
    cx, cy, r = discs[:, 0][None, None, :], discs[:, 1][None, None, :], discs[:, 2][None, None, :]
    fx, fy = cx - ax, cy - ay
    pos = dd > 0.0
    t = np.where(pos, (fx * dx + fy * dy) / np.where(pos, dd, 1.0), 0.0)
    t = np.minimum(np.maximum(t, 0.0), 1.0)
    px = ax + t * dx - cx
    py = ay + t * dy - cy
    return (px * px + py * py < r * r).any(2)


def obstacle_food_factor(gw: int, cell: float, discs: np.ndarray) -> np.ndarray:
    """세로 장애물 먹이 (모듈 docstring '야생 2단계' 3 의 4)). 셀 (iy, ix) 마다 표본점 ((ix + (a + 0.5)/OB_SAMPLES)·cell, (iy + (b + 0.5)/OB_SAMPLES)·cell)
    가운데 어느 원판 안(dx·dx + dy·dy ≤ r·r)인 수 n 으로 1 − n / OB_SAMPLES² (gw, gw). 원판이 없으면 모두 1. C++ FFoodGrid::ApplyObstacleFood."""
    S = OB_SAMPLES
    off = (np.arange(S, dtype=np.float64) + 0.5) / S
    coords = ((np.arange(gw, dtype=np.float64)[:, None] + off[None, :]) * float(cell)).reshape(-1)    # 표본 열 s = ix·S + a
    covered = np.zeros((gw * S, gw * S), dtype=bool)                                                  # [y 표본, x 표본]
    for cx, cy, r in discs:
        dx = coords - cx
        dy = coords - cy
        covered |= (dx * dx)[None, :] + (dy * dy)[:, None] <= r * r
    n = covered.reshape(gw, S, gw, S).sum(axis=(1, 3)).astype(np.float64)
    return 1.0 - n / float(S * S)


def obstacle_push_out(q: np.ndarray, discs: np.ndarray, body_r: float, size: float,
                      walls: np.ndarray | None = None) -> tuple[np.ndarray, int, int]:
    """세로 장애물 밀어내기 (모듈 docstring '야생 2단계' 3 의 5)). q (n, 2) 가운데 원판(R = r + body_r) 안인 개체를 가장 가까운 후보로 옮긴다. 후보 =
    원판마다 (c + (R + OB_EPS)·단위(q − c), q = c 면 (1, 0)) 하나와 c + (R + OB_EPS)·OB_RING[j] 8 개(원판 순서대로). 무대 [0, S]² 안 ∧ 모든 원판 밖 ∧
    walls(늑대의 은신처 막기 원 (x, y, R′), 없으면 None) 의 |q − c| < R′ 밖인 후보 가운데 거리² 가 가장 작은 것(같으면 앞). 반환 (새 q, 옮긴 수,
    후보가 없어 그대로 둔 수). C++ EcoWorldV3::ObstaclePushOut."""
    q = np.array(q, dtype=np.float64, copy=True)
    moved = failed = 0
    if not len(discs) or not len(q):
        return q, moved, failed
    inside = obstacle_inside(q, discs, body_r)
    for i in np.flatnonzero(inside):
        px, py = float(q[i, 0]), float(q[i, 1])
        cand = []
        for cx, cy, r in discs:
            rr = (float(r) + body_r) + OB_EPS
            vx, vy = px - float(cx), py - float(cy)
            n = math.sqrt(vx * vx + vy * vy)
            ux, uy = (vx / n, vy / n) if n > EPS else (1.0, 0.0)
            cand.append((float(cx) + rr * ux, float(cy) + rr * uy))
            for rx, ry in OB_RING:
                cand.append((float(cx) + rr * rx, float(cy) + rr * ry))
        C = np.asarray(cand, dtype=np.float64)
        ok = (C >= 0.0).all(1) & (C <= size).all(1) & ~obstacle_inside(C, discs, body_r)
        if walls is not None and len(walls):
            ex = C[:, 0:1] - walls[:, 0][None, :]
            ey = C[:, 1:2] - walls[:, 1][None, :]
            ok &= ~(np.sqrt(ex * ex + ey * ey) < walls[:, 2][None, :]).any(1)
        if not ok.any():
            failed += 1
            continue
        dx, dy = C[:, 0] - px, C[:, 1] - py
        q[i] = C[int(np.argmin(np.where(ok, dx * dx + dy * dy, np.inf)))]
        moved += 1
    return q, moved, failed


def pack_goals(wq, whead, leader, helper, tgt, p, disp, cov_c, cov_r, margin: float, size: float, wp: dict):
    """야생 2단계 2 늑대 무리 협동의 목표 (모듈 docstring '야생 2단계' 2). 순수 함수 — 세계(`_pack_step`)와 골든 내보내기가 함께 쓴다.
    wq·whead (M, 2) 늑대 이동 전 위치·heading, leader·helper (M,) bool, tgt (M,) 늑대의 이번 스텝 표적(앞장만 읽는다), p·disp (N, 2) 사슴 이동 뒤
    위치·이번 스텝 이동, cov_c (K, 2)·cov_r (K,) 은신처 원(사슴 반지름, 0 이하는 건너뛴다), margin = 늑대 몸 여유(막지 않으면 0), size = 무대 한 변,
    wp = wild_pack 계수. 반환 (help, wait, door, prey, dir): (M,) bool 셋, (M,) 고른 사슴(없으면 −1), (M, 2) 이동 방향(단위, 기다림이면 사슴 쪽).
    늑대마다 스칼라 식이라 C++ EcoThreatV3::PackGoals 와 같은 순서로 계산한다(골든 비트 동일).
    C++ 꼴: for (L 앞장, 슬롯 순) if (|p_t(L) − q| <= JoinR && (Best < 0 || d < BestD)) Best = t(L);
            U = |v| > Eps ? v/|v| : SafeDir(p − q_L);  Door = argmin_k e_k (0 < e_k <= DoorR, (c_k − p)·U / |c_k − p| >= DoorCos);
            G = Door ? c − (r + m)·(c − p)/|c − p| : p + Lead·U;  G = Clamp(G, 0, Size);
            |G − q| <= WaitR ? (Wait, Dir = SafeDir(p − q, Head)) : Dir = (G − q)/|G − q|"""
    M = len(wq)
    help_ = np.zeros(M, dtype=bool)
    wait = np.zeros(M, dtype=bool)
    door = np.zeros(M, dtype=bool)
    prey = np.full(M, -1, dtype=np.int64)
    dirv = np.zeros((M, 2))
    leaders = [int(x) for x in np.flatnonzero(leader)]
    if not leaders:
        return help_, wait, door, prey, dirv
    jr, lead, dr, dc, wr = (float(wp[k]) for k in ("join_r", "lead", "door_r", "door_cos", "wait_r"))
    margin, size = float(margin), float(size)
    K = len(cov_r)
    for m in np.flatnonzero(helper):
        m = int(m)
        qx, qy = float(wq[m, 0]), float(wq[m, 1])
        best, bd, bl = -1, 0.0, -1
        for lw in leaders:
            if lw == m:
                continue
            i = int(tgt[lw])
            dx, dy = float(p[i, 0]) - qx, float(p[i, 1]) - qy
            d = math.sqrt(dx * dx + dy * dy)
            if d <= jr and (best < 0 or d < bd):
                best, bd, bl = i, d, lw
        if best < 0:
            continue
        px, py = float(p[best, 0]), float(p[best, 1])
        vx, vy = float(disp[best, 0]), float(disp[best, 1])
        n = math.sqrt(vx * vx + vy * vy)
        if n > EPS:
            ux, uy = vx / n, vy / n
        else:
            ax, ay = px - float(wq[bl, 0]), py - float(wq[bl, 1])
            na = math.sqrt(ax * ax + ay * ay)
            ux, uy = (ax / na, ay / na) if na > EPS else (0.0, 0.0)
        bk, be, bex, bey, bdk = -1, 0.0, 0.0, 0.0, 0.0
        for k in range(K):
            r = float(cov_r[k])
            if not r > 0.0:
                continue
            ex, ey = float(cov_c[k, 0]) - px, float(cov_c[k, 1]) - py
            dk = math.sqrt(ex * ex + ey * ey)
            e = dk - r
            if e > 0.0 and e <= dr and (ex * ux + ey * uy) / dk >= dc and (bk < 0 or e < be):
                bk, be, bex, bey, bdk = k, e, ex, ey, dk
        if bk >= 0:
            rr = float(cov_r[bk]) + margin
            gx = float(cov_c[bk, 0]) - rr * (bex / bdk)
            gy = float(cov_c[bk, 1]) - rr * (bey / bdk)
        else:
            gx, gy = px + lead * ux, py + lead * uy
        gx = min(max(gx, 0.0), size)
        gy = min(max(gy, 0.0), size)
        hx, hy = gx - qx, gy - qy
        hn = math.sqrt(hx * hx + hy * hy)
        if hn <= wr:
            fx, fy = px - qx, py - qy
            fn = math.sqrt(fx * fx + fy * fy)
            dirv[m] = (fx / fn, fy / fn) if fn > EPS else (float(whead[m, 0]), float(whead[m, 1]))
            wait[m] = True
        else:
            dirv[m] = (hx / hn, hy / hn)
        help_[m] = True
        door[m] = bk >= 0
        prey[m] = best
    return help_, wait, door, prey, dirv


def wf_edge_steer(pos: np.ndarray, d: np.ndarray, size: float, edge_r: float) -> np.ndarray:
    """야생 (w3) 10-16 가장자리 굽히기 (모듈 docstring '야생 1단계' (w3) edge_r). pos (K, 2) 위치, d (K, 2) 단위 방향 → (K, 2) 단위 방향.
    축 a 마다 가까운 벽까지 거리 e_a = min(p_a, size − p_a) < edge_r 이면 안쪽 부호 n_a(p_a ≤ size − p_a 면 +1, 아니면 −1)와 가까움
    w_a = 1 − e_a / edge_r, 아니면 n_a = w_a = 0.
      1) 모서리(w_x > 0, w_y > 0)이고 d 가 한 벽 쪽이라도 향하면(d_a·n_a < 0): 벽을 따라 모서리를 빠져나오는 두 방향 (n_x, 0)·(0, n_y) 가운데
         d 와 내적이 큰 쪽 t(d_x·n_x ≥ d_y·n_y 면 x 쪽)를 섞는다: s = d + (2·min(w_x, w_y))·t. 아니면 s = d
      2) x 축, 그다음 y 축(o = 다른 축): s_a·n_a < 0 이면 막힌 몫 b = (−s_a·n_a)·w_a 를 벽 쪽 성분에서 빼고(s_a += b·n_a) 다른 축에 벽을
         따라 더한다(s_o += b·σ, σ = s_o 의 부호, s_o = 0 이면 무대 가운데 쪽 — p_o ≤ size/2 면 +1, 아니면 −1)
      3) 단위화(normalize). 0 이면 d 그대로
    edge_r ≤ 0 이면 d 그대로. 난수 없음.
    C++ 꼴: for a: E = min(P[a], Size - P[a]); if (E < EdgeR) { N[a] = P[a] <= Size - P[a] ? 1 : -1; W[a] = 1 - E / EdgeR; }
           S = D; if (W.X > 0 && W.Y > 0 && (D.X*N.X < 0 || D.Y*N.Y < 0)) { if (D.X*N.X >= D.Y*N.Y) S.X += 2*min(W)*N.X; else S.Y += 2*min(W)*N.Y; }
           for a in (X, Y): if (S[a]*N[a] < 0) { B = (-S[a]*N[a])*W[a]; S[a] += B*N[a]; S[o] += B*Sign(S[o], P[o] <= Size/2); }
           Out = S.GetSafeNormal(); if (Out.IsZero()) Out = D;"""
    if edge_r <= 0.0 or len(d) == 0:
        return d
    e = np.minimum(pos, size - pos)
    near = e < edge_r
    n = np.where(near, np.where(pos <= size - pos, 1.0, -1.0), 0.0)
    w = np.where(near, 1.0 - e / edge_r, 0.0)
    s = d.copy()
    corner = (w[:, 0] > 0.0) & (w[:, 1] > 0.0) & ((d[:, 0] * n[:, 0] < 0.0) | (d[:, 1] * n[:, 1] < 0.0))
    if corner.any():
        c = np.flatnonzero(corner)
        ux = d[c, 0] * n[c, 0] >= d[c, 1] * n[c, 1]
        k = 2.0 * np.minimum(w[c, 0], w[c, 1])
        s[c[ux], 0] += k[ux] * n[c[ux], 0]
        s[c[~ux], 1] += k[~ux] * n[c[~ux], 1]
    for a in (0, 1):
        o = 1 - a
        wall = s[:, a] * n[:, a] < 0.0
        if not wall.any():
            continue
        b = np.where(wall, (-s[:, a] * n[:, a]) * w[:, a], 0.0)
        sg = np.where(s[:, o] > 0.0, 1.0, np.where(s[:, o] < 0.0, -1.0, np.where(pos[:, o] <= 0.5 * size, 1.0, -1.0)))
        s[:, a] = np.where(wall, s[:, a] + b * n[:, a], s[:, a])
        s[:, o] = np.where(wall, s[:, o] + b * sg, s[:, o])
    out = normalize(s)
    return np.where(((out * out).sum(1) > EPS * EPS)[:, None], out, d)


# 야생 2단계 사냥 성공률 통계(모듈 docstring '야생 2단계'). hunt_stats 의 칸 순서: 시작·끝·성공·사냥 밖 포획
HUNT_KEYS = ("starts", "ends", "success", "outside")


def hunt_update(on: np.ndarray, running: np.ndarray, caught: np.ndarray):
    """늑대마다 사냥 한 번 셈 (모듈 docstring '야생 2단계' 사냥 성공률). 통계 전용이고 동역학과 무관하다.
    on = 지난 스텝 끝에 사냥이 이어지는 중, running = 이번 스텝 전력 걸음(추격형이 표적을 쫓음·잠행형 돌진·플레이어 돌진), caught = 이번 스텝에
    이 늑대가 잡음. 모두 (M,) bool. 반환 (새 on, 시작, 끝, 성공, 사냥 밖 포획) — 뒤 넷은 (M,) bool.
      시작 = running ∧ ¬on. 이번 스텝 사냥 중 h = on ∨ running. 성공 = caught ∧ h, 사냥 밖 포획 = caught ∧ ¬h, 실패 = h ∧ ¬caught ∧ ¬running.
      끝 = 성공 ∨ 실패, 새 on = h ∧ ¬끝.
    C++ 꼴: const bool bStart = bRun && !bOn; const bool bH = bOn || bRun; bSuccess = bCaught && bH; bOutside = bCaught && !bH;
            bEnd = bSuccess || (bH && !bCaught && !bRun); bOn = bH && !bEnd;"""
    on = np.asarray(on, dtype=bool)
    running = np.asarray(running, dtype=bool)
    caught = np.asarray(caught, dtype=bool)
    start = running & ~on
    h = on | running
    success = caught & h
    outside = caught & ~h
    end = success | (h & ~caught & ~running)
    return h & ~end, start, end, success, outside


def wild_days_to_steps(days: float, period: int) -> int:
    """게임 하루 단위 계수 → 스텝 = 반올림(일 × 하루 스텝), 0.5 는 올림 (모듈 docstring '야생 1단계')."""
    return int(math.floor(float(days) * int(period) + 0.5))


def night_delays(seed: int, n: int, max_delay: int) -> np.ndarray:
    """realism_night 의 늑대별 잠·기상 지연 δ_m = H(606, 세계 시드, m) mod (max_delay + 1) ∈ [0, max_delay] (int64, m = 위협 슬롯
    0..n−1). H 는 repertoire.mix_chain(SplitMix64 사슬, 사건 결정 지연과 같은 식). C++ 꼴: Mix64Chain(0, 606, Seed, Slot) % (D + 1)."""
    if max_delay <= 0 or n == 0:
        return np.zeros(n, dtype=np.int64)
    h = rep.mix_chain(NIGHT_TAG, np.int64(seed), np.arange(n, dtype=np.int64))
    return (h % np.uint64(max_delay + 1)).astype(np.int64)


def daynight_phase(t: int, period: int, offset: int, tw_steps: int) -> tuple[float, int]:
    """스텝 t 의 (어둠 d, 다음 전환까지 남은 스텝 r) (계획서 4.9.2). 낮 고정 세계는 부르지 않는다(d = 0).

    s = (t + o) mod T, 낮 = s < T/2. e = s mod (T/2) 는 지난 전환 뒤 스텝, r = T/2 − e ∈ [1, T/2] 는 다음 전환까지.
    k = min(e, r), τ = 박명 폭(정수 스텝). 낮이면 d = clip(0.5 − k/(2τ), 0, 1), 밤이면 clip(0.5 + k/(2τ), 0, 1) —
    전환 순간 0.5, 전환 앞뒤 τ 스텝(계 0.1·T)에 걸쳐 0 과 1 을 선형으로 잇는다.
    C++ 꼴: e = Now − PhaseStart, r = PhaseEnd − Now (스텝), bNight = Phase == Night.
    """
    h = period // 2
    s = (int(t) + int(offset)) % period
    e = s % h
    r = h - e
    k = min(e, r)
    x = k / (2.0 * tw_steps)
    d = min(0.5 + x, 1.0) if s >= h else max(0.5 - x, 0.0)
    return d, r


def daynight_draws(dn: dict, seed: int, n_agents: int) -> dict:
    """세계 시드 하나가 정하는 낮밤 값(`World._daynight_reset` 이 같은 순서로 뽑는 값)을 세계를 만들지 않고 낸다.

    daynight 스트림 part 0 에서 정확히 3개: u0 → 낮 고정(u0 < fixed_day_frac), u1 → T = periods[⌊u1·n⌋],
    u2 → o = ⌊u2·T⌋. start_induce > 0 이면 part 2 에서 u → 유도(u < start_induce, 낮 고정이 아닐 때만)와 개체
    에너지 n_agents 개(U[0.2, 0.5], 늘 뽑는다). 유도면 o = T/2 − ⌈0.1·T⌉ (해 지기 0.1·T 스텝 전에 시작한다).
    """
    g = feature_stream(int(seed), "daynight", 0)
    u0, u1, u2 = g.random(3)
    per = dn["periods"]
    i = min(int(u1 * len(per)), len(per) - 1)
    T = per[i]
    out = dict(day_fixed=bool(u0 < dn["fixed_day_frac"]), period=T, offset=min(int(u2 * T), T - 1),
               tw_steps=dn["tw_steps"][i], induced=False, energy=None)
    if dn["start_induce"] > 0.0:
        g2 = feature_stream(int(seed), "daynight", 2)
        ui = float(g2.random())
        energy = g2.uniform(INDUCE_ENERGY[0], INDUCE_ENERGY[1], n_agents)
        if ui < dn["start_induce"] and not out["day_fixed"]:
            out.update(induced=True, energy=energy, offset=T // 2 - int(math.ceil(0.1 * T)))
    return out


def daynight_seg_edges(detect_night: float, tol: float = 1e-5) -> tuple[float, float]:
    """관측 visibility(float32)로 위상 구간을 나누는 문턱 (밤 | 박명 | 낮). `np.digitize(vis, edges)` 가 0 밤, 1 박명,
    2 낮을 낸다: 밤 = vis ≤ 1 − 0.8·detect_night, 낮 = vis ≥ 1 − 0.2·detect_night (d 구간과 같다). d 의 이웃 값 사이
    간격(≥ detect_night/(2τ))보다 훨씬 작은 tol 로 float32 반올림을 흡수한다. detect_night = 0 이면 나눌 수 없다.
    """
    if detect_night <= 0.0:
        raise ValueError("detect_night = 0 이면 visibility 가 늘 1 이라 위상 구간을 관측으로 나눌 수 없다")
    return (1.0 - DN_EDGES[1] * detect_night + tol, 1.0 - DN_EDGES[0] * detect_night - tol)


class World:
    """N=128 슬롯 고정, 죽으면 그 슬롯에 리스폰 (§4.3).

    `step()` 은 항상 [0,1] 행동을 받는다 (§1.3). (-3,3) 출력의 sigmoid 변환은
    VecEnv 래퍼(§6.2)의 책임이지 이 클래스의 책임이 아니다.
    """

    def __init__(self, cfg, seeds=None, meta_seed: int = 0):
        self.cfg = cfg
        if seeds is None:
            lo, hi = cfg.train_seeds
            seeds = range(lo, hi)
        self.seeds = np.asarray(list(seeds), dtype=np.int64)
        self.meta = np.random.default_rng(meta_seed)
        self.N = int(cfg.N)
        self.features: Features = features_of(cfg)
        # 켠 기능의 계수(yaml 원본). 꺼진 기능은 None 이고 그 기능의 코드 경로를 타지 않는다.
        self._fv = _food_v_params(self.features.params("food_v")) if self.features.enabled("food_v") else None
        self._sp = _speed_params(self.features.params("speed")) if self.features.enabled("speed") else None
        self._vg = (_vigil_params(self.features.params("vigilance"), cfg.fov_deg)
                    if self.features.enabled("vigilance") else None)
        self._vw = (_window_params(self.features.params("vigil_window"), self.features)
                    if self.features.enabled("vigil_window") else None)
        self._dn = (_daynight_params(self.features.params("daynight"), self.features)
                    if self.features.enabled("daynight") else None)
        self._ps = (_pred_sleep_params(self.features.params("pred_sleep"), self.features)
                    if self.features.enabled("pred_sleep") else None)
        # v3 R0: 행동 레퍼토리(repertoire), 위협 유형(threats). 둘 중 하나라도 켜면 포식자 스텝은 _step_predators_v3 다
        self._rp = (rep.parse_params(self.features.params("repertoire"), self.features)
                    if self.features.enabled("repertoire") else None)
        self._th = (_threats_params(self.features.params("threats"), self.features)
                    if self.features.enabled("threats") else None)
        # v3 R3 (j) 늑대 먹는 시간(10-15): 잡은 뒤 쿨다운 pred_eat_cd 동안 늑대가 제자리에서 먹는다. 끈 세계는 False 이고 그 코드 경로를 타지 않는다
        self._eat_in_place = bool(self._th is not None and self._th["eat_in_place"])
        if self._eat_in_place:
            cd = cfg.pred_eat_cd
            if isinstance(cd, bool) or not isinstance(cd, (int, np.integer)) or cd < 0:
                raise ValueError(f"threats.eat_in_place 를 켜면 pred_eat_cd 는 0 이상의 정수(스텝)여야 한다. 받은 값: {cd!r}")
        self._v3p = self._rp is not None or self._th is not None
        # v3 R2: 노려보기 대치(stare_down, M7), 동족 경보(alarm, M8). 끈 세계는 None 이고 그 코드 경로를 타지 않는다
        self._sd = (_stare_params(self.features.params("stare_down"), self.features)
                    if self.features.enabled("stare_down") else None)
        self._al = (_alarm_params(self.features.params("alarm"), self.features)
                    if self.features.enabled("alarm") else None)
        # v3 현실성 1단계(모듈 docstring realism_*): 시야(a)·청각(b)·은신처 안전(c)·은신처 먹이 부족(e)·늑대 밤잠 점진화(d). 끈 규칙은
        # None 이고 그 코드 경로를 타지 않는다
        f = self.features
        self._zv = (_rz_vision_params(f.params("realism_vision"), f, cfg) if f.enabled("realism_vision") else None)
        self._zh = (_rz_hearing_params(f.params("realism_hearing"), f) if f.enabled("realism_hearing") else None)
        self._zs = (_rz_shelter_params(f.params("realism_shelter"), f) if f.enabled("realism_shelter") else None)
        self._zf = (_rz_cover_food_params(f.params("realism_cover_food"), f) if f.enabled("realism_cover_food") else None)
        self._zn = (_rz_night_params(f.params("realism_night"), f, self._ps) if f.enabled("realism_night") else None)
        self._rz = any(x is not None for x in (self._zv, self._zh, self._zs, self._zf, self._zn))
        # v3 R3 세계(모듈 docstring 'R3 세계'): 추격 고정 (f), 지형 (h), 늑대 은신처 진입 금지 (c′, realism_shelter 선택 키), 은신처 먹이
        # 배수 뽑기 (e′, realism_cover_food 선택 키). 끈 규칙은 None·False 이고 그 코드 경로를 타지 않는다
        self._zc = (_rz_chase_params(f.params("realism_chase"), f) if f.enabled("realism_chase") else None)
        self._zt = (_rz_terrain_params(f.params("realism_terrain"), f) if f.enabled("realism_terrain") else None)
        self._zw = bool(self._zs is not None and self._zs["block_predators"])
        # (c″) 늑대 몸 여유(단위): 막는 위협에게만 원 반지름이 r + 이 값이다. 0 이면 10-16 그대로
        self._zw_m = float(self._zs["wolf_margin"]) if self._zw else 0.0
        self._zf_range = self._zf is not None and self._zf["frac_range"] is not None
        self._r3 = self._zc is not None or self._zt is not None or self._zw or self._zf_range
        # 언리얼 통합 무대 거울(모듈 docstring '통합 무대'): 부활 없음·EMA 분모·시작 위상·은신처·늑대 구성·시작 배치·방향. 끈 세계는 None 이고
        # 그 코드 경로를 타지 않는다
        self._ist = (_ist_params(f.params("integrated_stage"), f) if f.enabled("integrated_stage") else None)
        # 야생 1단계(모듈 docstring '야생 1단계'): 지방 비축 (w1)·늑대 포만 (w2)·도주 반사 거리 (w3). 끈 규칙은 None 이고 그 코드 경로를 타지 않는다
        self._wr = (_wild_reserve_params(f.params("wild_reserve"), f) if f.enabled("wild_reserve") else None)
        self._ws = (_wild_satiation_params(f.params("wild_satiation"), f) if f.enabled("wild_satiation") else None)
        self._wf = (_wild_flight_params(f.params("wild_flight"), f) if f.enabled("wild_flight") else None)
        # 야생 2단계 2(모듈 docstring '야생 2단계' 2): 늑대 무리 협동 사냥. 끈 세계는 None 이고 그 코드 경로를 타지 않는다
        self._wp = (_wild_pack_params(f.params("wild_pack"), f) if f.enabled("wild_pack") else None)
        # 야생 2단계 3(모듈 docstring '야생 2단계' 3): 세로 장애물. 끈 세계는 None 이고 그 코드 경로를 타지 않는다(World.obstacles 는 늘 빈 목록)
        self._ob = (_obstacles_params(f.params("obstacles"), f) if f.enabled("obstacles") else None)
        # 통계·진단 전용(설정 아님, 동역학과 무관): 참이면 기하에 사슴 × 위협 보임 행렬 wf_pvis 를 남긴다(실행기 results/v3/wild1 이 켠다)
        self.keep_pair_vis = False
        self.alive = None
        self._rs = None
        self.act_names: tuple[str, ...] = action_names(self.features)
        self.act_dim = len(self.act_names)
        self.obs_names: tuple[str, ...] = obs_names(self.features)
        self.obs_dim = len(self.obs_names)
        # 경계 행동 열. vigilance 를 끈 세계와 v2.2r action false 세계는 None 이다(경계가 일어나지 않는다)
        self._act_vig = self.act_names.index("vigilance") if "vigilance" in self.act_names else None
        # v2.4 관측 열 (이름으로 찾는다). daynight 를 끈 세계는 None 이다
        self._obs_vis = self.obs_names.index("visibility") if self._dn is not None else None
        self._obs_tt = self.obs_names.index("to_transition") if self._dn is not None else None
        # v3 추가 관측 9칸의 첫 열 (obs_extra false 면 None)
        self._obs_rep = (self.obs_names.index(rep.OBS_EXTRA_NAMES[0])
                         if self._rp is not None and self._rp["obs_extra"] else None)
        # v3 R2 관측 alarm_heard 열 (alarm 을 켜고 obs_extra 가 true 일 때만)
        self._obs_alarm = (self.obs_names.index(rep.OBS_ALARM_NAME) if rep.OBS_ALARM_NAME in self.obs_names else None)
        self.reset()

    # ------------------------------------------------------------------ #
    # reset / 세계 생성
    # ------------------------------------------------------------------ #

    def reset(self) -> np.ndarray:
        """§4.4 — 시드 하나가 무작위화 파라미터와 세계 배치를 모두 결정한다 (§3.5)."""
        cfg = self.cfg
        seed = int(self.meta.choice(self.seeds))
        r = self.rng = np.random.default_rng(seed)
        self.seed = seed
        # 기능별 난수 스트림은 처음 쓸 때 만든다(feature_rng). 세계를 새로 뽑으면 처음부터 다시 시작한다.
        self._feature_rngs: dict[tuple[str, int], np.random.Generator] = {}

        rd = cfg.rand
        self.size = float(r.uniform(*rd["world_size"]))
        self.M = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
        self.pred_speed_mult = float(r.uniform(*rd["pred_speed_mult"]))
        self.ranged_frac = float(r.uniform(*rd["ranged_frac"]))
        self.cover_frac_target = float(r.uniform(*rd["cover_frac"]))
        self.food_regen_mult = float(r.uniform(*rd["food_regen_mult"]))

        self._build_world()
        ist = self._ist
        if ist is not None:
            # 통합 무대 (n)(p)(q): 은신처·시작 자리·시작 방향을 덮는다(v1 뽑기는 그대로, 자기 스트림만). 현실성 (e)·food_v·벽 밀어내기 전
            self._ist_layout_reset()
            # (k) 부활 없음의 산 슬롯 훅. 부활 있는 세계는 None 이다
            self.alive = None if ist["respawn"] else np.ones(self.N, dtype=bool)
            if self.alive is not None:
                self.death_t = np.full(self.N, -1, dtype=np.int64)
                self.death_cause = np.zeros(self.N, dtype=np.int8)
        self._obstacles_reset()             # 야생 2단계 3: 세로 장애물 원판·먹이(끈 세계는 늘 빈 목록, 난수 없음)
        if self._zt is not None:
            self._rz_terrain_reset()        # v3 R3 (h): 지형 격자(자기 스트림만, 은신처·먹이와 독립)
        if self._zf is not None:
            self._rz_cover_food_apply()     # v3 현실성 (e): 은신처 셀 먹이 용량·재생 (food_v 의 V 초기화 전)
        if self._fv is not None:
            self._food_v_reset()
        if self._sp is not None:
            # v2.1 스텝 뒤 훅 (replay_v2): 실제 보행, 명령 보행, 적용 속도. 첫 스텝 전에는 정지·0 으로 둔다.
            self.gait = np.zeros(self.N, dtype=np.int8)
            self.gait_cmd = np.zeros(self.N, dtype=np.int8)
            self.vel = np.zeros((self.N, 2))
        if self._vg is not None:
            # v2.2 개체별 상태 (`_perceive`): threat_recency, ThreatDir(마지막 위협 방향, 단위벡터. 본 적 없으면 0),
            # 다음 관측의 시야(True = 경계 시야, 직전 스텝에 경계했다). 처음에는 모두 0·기본 시야다.
            self.threat = np.zeros(self.N)
            self.threat_dir = np.zeros((self.N, 2))
            self._wide = np.zeros(self.N, dtype=bool)
            # 통계 전용(vigil_stats *_truth, 관측·동역학에 들어가지 않는다): 결정 때 반경 안 포식자 유무(FOV 무시)와
            # 그 흔적(threat_recency 와 같은 갱신·decay·리스폰 0). 시야(경계 360°)와 무관한 기준 구간을 만든다
            self._near = np.zeros(self.N, dtype=bool)
            self._tr_truth = np.zeros(self.N)
            # 스텝 뒤 훅 (replay_v2): 이번 스텝의 경계, 시선(= 스텝 뒤 heading), 적용 속도(speed 를 끈 세계에도 둔다)
            self.vigilant = np.zeros(self.N, dtype=bool)
            self.gaze = self.head.copy()
            if self._sp is None:
                self.vel = np.zeros((self.N, 2))
        if self._vw is not None:
            # v2.2r 스텝 뒤 훅 (replay_v2): 이번 스텝의 결정 때 창, 반사 돌아보기가 heading 을 바꾼 개체
            self.window = np.zeros(self.N, dtype=bool)
            self.looked = np.zeros(self.N, dtype=bool)
        # v1 포식자 수(threats 의 플레이어 칸을 빼고). threats 를 끈 세계는 늘 self.M 과 같다
        self.M_base = self.M
        if self._v3p:
            # v3 포식자 스텝: v1 원거리형 배치(잠행형이 덮기 전, v1 스트림 호출 모양을 정한다)
            self._pred_ranged_v1 = self.pred_ranged.copy()
        if self._ps is not None:
            self._pred_sleep_reset()
        if self._th is not None:
            self._threats_reset()           # 포식자 밤잠 배치(M 개) 뒤, 어둠을 정하기 전에 잠행형·플레이어를 정한다
            if ist is not None and ist["wolf_kinds"] is not None:
                self._ist_wolf_kinds()      # 통합 무대 (o): 늑대 구성을 슬롯 번갈아로 덮는다(threats 뽑기는 그대로)
        if self._sd is not None:
            self._stare_reset()             # 위협 수 M(플레이어 칸 포함)이 정해진 뒤
        if self._zw:
            self._rz_wall_reset()           # v3 R3 (c′): 은신처 원 안에 놓인 위협을 둘레 밖으로(난수 없음)
        if self._zc is not None:
            self._rz_chase_reset()          # v3 R3 (f): 위협별 추격 고정 상태(크기 M)
        if self._ob is not None:
            self._ob_place_agents()         # 야생 2단계 3 의 5): 원판 안 사슴·늑대를 밖으로(은신처 밀어내기 뒤, 난수 없음)
        if self._v3p:
            self.pred_vel = np.zeros((self.M, 2))   # 포식자의 지난 스텝 이동(관측 pred_approach)
            # 야생 2단계 통계 전용: 늑대마다 사냥이 이어지는 중인가(`hunt_update`). 처음에는 아니다
            self._hunt_on = np.zeros(self.M, dtype=bool)
        if self._zh is not None:
            # v3 현실성 (b) 스텝 뒤 훅: 위협이 지난 스텝에 전력 걸음이었나(추격형의 표적 추격, 잠행형 돌진, 플레이어 돌진). 처음에는 아니다
            self.pred_running = np.zeros(self.M, dtype=bool)
        if self._zn is not None:
            self._rz_night_reset()          # 위협 수 M(플레이어 칸 포함)이 정해진 뒤, 첫 어둠(_daynight_reset) 전에
        if self._dn is not None:
            self._daynight_reset()
        if self._rp is not None:
            self._repertoire_reset()
        if self._al is not None:
            self._alarm_reset()
        if self._wr is not None or self._ws is not None or self._wf is not None or self._wp is not None:
            self._wild_reset()              # 야생 1단계·2단계 2: 하루 길이(_daynight_reset)·위협 수 M 이 정해진 뒤
        self._reset_stats()
        self._g = self._geometry()
        if self._vg is not None:
            self._perceive(self._g)
        if self._rp is not None:
            rep.perceive(self._rs, self._rp, self._g)
        self._obs = self._obs_from(self._g)
        return self._obs

    def feature_rng(self, name: str, part: int = 0) -> np.random.Generator:
        """기능 `name` 의 난수 스트림. 이 세계의 시드에서 나오고 다른 기능·v1 스트림과 독립이다.

        같은 기능에 나중에 난수를 더할 때는 새 `part` 를 쓴다 (`env_v2/features.py` 규칙 3).
        """
        _check_name(name)
        _check_part(part)                   # 캐시를 찾기 전에 검사한다(True·1.0 은 키 1 과 같게 해시된다)
        key = (name, int(part))
        g = self._feature_rngs.get(key)
        if g is None:
            g = self._feature_rngs[key] = feature_stream(self.seed, name, part)
        return g

    def _build_world(self) -> None:
        cfg, r = self.cfg, self.rng
        N, size = self.N, self.size

        # --- 먹이 격자 (§4.2) ---
        # 셀마다 독립 균등난수를 깔면 먹이가 온 맵에 고르게 깔려서 따라갈 기울기가
        # 백색잡음이 된다 (측정: forage가 아무 이득이 없었다). 저주파 노이즈를
        # 문턱값으로 잘라 **패치**를 만들고, 재생은 그 용량(capacity)을 향해 간다.
        # 그래야 고갈된 패치가 비어 있는 채로 남고 먹이 탐색이 실제 문제가 된다.
        self.gw = int(np.ceil(size / cfg.food_cell))
        m = self._smooth(r.random((self.gw, self.gw)), int(cfg.food_patch_blur))
        m = (m - m.min()) / max(m.max() - m.min(), EPS)
        t = float(cfg.food_patch_threshold)
        self.food_cap = np.clip((m - t) / (1.0 - t), 0.0, 1.0)
        self.food = self.food_cap.copy()
        cc = (np.arange(self.gw) + 0.5) * cfg.food_cell      # 셀 중심 좌표
        self._cell_x, self._cell_y = np.meshgrid(cc, cc)     # 둘 다 (gw,gw)

        # --- 은신처 (§4.2): 셀 마스크 면적이 목표 비율에 닿을 때까지 원을 놓는다 ---
        centers, radii = [], []
        mask = np.zeros((self.gw, self.gw), dtype=bool)
        for _ in range(int(cfg.cover_max_count)):
            if mask.mean() >= self.cover_frac_target:
                break
            c = r.uniform(0.0, size, 2)
            rad = float(r.uniform(cfg.cover_r_min, cfg.cover_r_max))
            centers.append(c)
            radii.append(rad)
            mask |= (self._cell_x - c[0]) ** 2 + (self._cell_y - c[1]) ** 2 <= rad * rad
        self.cov_c = np.asarray(centers, dtype=np.float64).reshape(-1, 2)
        self.cov_r = np.asarray(radii, dtype=np.float64).reshape(-1)
        self.cover_cell = mask
        self.cover_frac_actual = float(mask.mean())

        # 은신처 셀은 재생 속도 0.3배 (§4.2)
        self.regen_field = cfg.food_regen_base * self.food_regen_mult * np.where(
            self.cover_cell, cfg.food_cover_regen_mult, 1.0
        )

        # --- 초식 (§4.3) ---
        self.pos = r.uniform(0.0, size, (N, 2))
        ang = r.uniform(0.0, 2 * np.pi, N)
        self.head = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy = np.full(N, float(cfg.init_energy))
        self.repro_cd = np.zeros(N, dtype=np.int32)

        # --- 포식자 (§4.2) ---
        M = self.M
        self.pred_pos = r.uniform(0.0, size, (M, 2))
        pang = r.uniform(0.0, 2 * np.pi, M)
        self.pred_head = np.stack([np.cos(pang), np.sin(pang)], 1)
        self.pred_ranged = r.random(M) < self.ranged_frac
        base = cfg.herb_speed * self.pred_speed_mult
        self.pred_speed = np.where(self.pred_ranged, base * cfg.pred_ranged_speed_mult, base)
        self.pred_catch_r = np.where(
            self.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r
        )
        # 포식 후 식사 쿨다운. §4.4가 포식자 속도를 herb_speed의 1.0~1.4배로 고정하므로
        # 한번 붙잡히면 도주로는 벗어날 수 없다. 쿨다운이 포식 압력의 상한을 정한다.
        self.pred_cd = np.zeros(M, dtype=np.int32)

        # --- 지역 피식 EMA (§3.1) ---
        self.pred_ema = 0.0
        self.t = 0

    def _left_half(self) -> np.ndarray:
        """셀 중심이 맵 왼쪽 절반(x < size/2)인 셀 (gw,gw). v2.3 지역 전까지 지역 대용이다 (계획서 0-6)."""
        return self._cell_x < 0.5 * self.size

    def _obstacles_reset(self) -> None:
        """야생 2단계 3 세로 장애물 (모듈 docstring '야생 2단계' 3 의 1)·4)). `_build_world`·통합 무대 배치 뒤, 은신처 먹이 부족 (e)·food_v 전에 부른다.
        끈 세계는 `World.obstacles` 가 늘 (0, 3) 이고 난수를 쓰지 않는다. 켠 세계: fixed 가 있으면 그 원판(난수 없음), 없으면 `obstacle_layout`(자기
        스트림 part 0). no_food 면 셀 용량 × `obstacle_food_factor`, 먹이 ← min(먹이, 용량). 훅 ob_food_factor (gw, gw)(짝 비교 지도 덮기가 다시 건다)."""
        ob = self._ob
        if ob is None:
            self.obstacles = np.zeros((0, len(OBSTACLE_COLUMNS)), dtype=np.float64)
            return
        if ob["fixed"] is not None:
            self.obstacles = ob["fixed"].copy()
        else:
            self.obstacles = obstacle_layout(self.feature_rng("obstacles", 0), self.size, self.cov_c, self.cov_r, ob)
        if ob["no_food"]:
            self.ob_food_factor = obstacle_food_factor(self.gw, float(self.cfg.food_cell), self.obstacles)
            self.food_cap = self.food_cap * self.ob_food_factor
            np.minimum(self.food, self.food_cap, out=self.food)
        else:
            self.ob_food_factor = np.ones((self.gw, self.gw))
        # 통계 전용(obstacle_stats)
        self._ob_deer_hit = self._ob_deer_back = self._ob_wolf_hit = self._ob_wolf_back = self._ob_wolf_dead = 0
        self._ob_deer_steps = self._ob_wolf_steps = 0
        self._ob_eye_pairs = self._ob_eye_blocked = self._ob_tgt_pairs = self._ob_tgt_blocked = 0
        self._ob_push_moved = self._ob_push_failed = 0

    def _ob_walls(self) -> np.ndarray | None:
        """늑대 밀어내기 후보가 피할 은신처 막기 원 (K, 3) [x, y, r + wolf_margin] — 은신처 막기(c′)를 켠 세계만, 아니면 None."""
        if not self._zw or not len(self.cov_r):
            return None
        return np.c_[self.cov_c, self._rz_wall_r()]

    def _ob_place_agents(self) -> None:
        """야생 2단계 3 의 5) reset: 원판(r + body_r) 안의 사슴·늑대를 `obstacle_push_out` 로 옮긴다(은신처 밖 밀어내기 `_rz_wall_reset` 뒤). 막는 늑대
        (_zw_sel)는 은신처 막기 원 밖 후보만 쓴다. 난수 없음."""
        disc, body = self.obstacles, self._ob["body_r"]
        if not len(disc):
            return
        self.pos, m1, f1 = obstacle_push_out(self.pos, disc, body, self.size)
        walls = self._ob_walls()
        if self.M:
            sel = self._zw_sel if walls is not None else np.ones(self.M, dtype=bool)
            q = self.pred_pos.copy()
            q[sel], m2, f2 = obstacle_push_out(q[sel], disc, body, self.size, walls)
            q[~sel], m3, f3 = obstacle_push_out(q[~sel], disc, body, self.size)
            self.pred_pos = q
        else:
            m2 = f2 = m3 = f3 = 0
        self._ob_push_moved += m1 + m2 + m3
        self._ob_push_failed += f1 + f2 + f3

    def _ob_seg_blocked(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """선분 a_i → b_i (n, 2) 쌍마다 원판에 가리나 (n,) bool — `sight_blocked` 와 같은 식(대각 성분)."""
        if not len(a):
            return np.zeros(0, dtype=bool)
        disc = self.obstacles
        ax, ay = a[:, 0][:, None], a[:, 1][:, None]
        dx = b[:, 0][:, None] - ax
        dy = b[:, 1][:, None] - ay
        dd = dx * dx + dy * dy
        cx, cy, r = disc[:, 0][None, :], disc[:, 1][None, :], disc[:, 2][None, :]
        fx, fy = cx - ax, cy - ay
        pos = dd > 0.0
        t = np.where(pos, (fx * dx + fy * dy) / np.where(pos, dd, 1.0), 0.0)
        t = np.minimum(np.maximum(t, 0.0), 1.0)
        px = ax + t * dx - cx
        py = ay + t * dy - cy
        return (px * px + py * py < r * r).any(1)

    def _ob_occlude(self, vis: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, int, int]:
        """보임 행렬 vis (n, m)(a_i 가 b_j 를 봄) 가운데 참인 쌍만 원판 시선을 잰다. 반환 (가린 쌍을 지운 vis, 잰 쌍, 가린 쌍)."""
        ii, jj = np.nonzero(vis)
        if not len(ii):
            return vis, 0, 0
        blk = self._ob_seg_blocked(a[ii], b[jj])
        if blk.any():
            vis = vis.copy()
            vis[ii[blk], jj[blk]] = False
        return vis, len(ii), int(np.count_nonzero(blk))

    def _ist_layout_reset(self) -> None:
        """통합 무대 (n) 은신처 quad, (p) 시작 배치 stage, (q) 시작 방향 golden (모듈 docstring '통합 무대'). `_build_world` 바로 뒤에 부른다 —
        v1 뽑기(은신처 원·위치·각)는 이미 끝났고 그 결과만 덮는다(features.py 규칙 2). 난수는 자기 스트림 part 0(stage 의 후보)만 쓴다.
        훅: stage_complete(stage 를 다 채웠나, 안 쓰면 None). 포식자 칸은 v1 포식자 M 개(플레이어 칸은 threats 가 뒤에 붙인다)."""
        ist, cfg = self._ist, self.cfg
        size = self.size
        c = 0.5 * size
        if ist["cover_layout"] == "quad":
            # C++ 우리 은신처(EcoPolicyV3IntegratedSubsystem.cpp): 원 k 의 시도 a — 각 45° + 90°·k ± 15°·⌈a/2⌉(짝수 +), 거리 0.25·S·√2(12번째
            # 시도부터 0.75 배). 무대 안 여유 R + 1, 앞 원과 2R + 2 이상이면 놓고 다음 원으로. 지면 검사가 없다
            R = min(max(ist["cover_r_frac"] * size, float(cfg.cover_r_min)), float(cfg.cover_r_max))
            centers: list[tuple[float, float]] = []
            for k in range(ist["cover_count"]):
                base = 0.25 * math.pi + 0.5 * math.pi * k
                for a in range(IST_COVER_TRIES):
                    turn = (1.0 if a % 2 == 0 else -1.0) * ((a + 1) // 2) * math.radians(IST_COVER_TURN_DEG)
                    rad = 0.25 * size * math.sqrt(2.0) * (1.0 if a < IST_COVER_SHRINK_AT else 0.75)
                    hx, hy = c + rad * math.cos(base + turn), c + rad * math.sin(base + turn)
                    half = c - (R + IST_COVER_MARGIN)
                    if abs(hx - c) > half or abs(hy - c) > half:
                        continue
                    if any(math.hypot(px - hx, py - hy) < 2.0 * R + IST_COVER_GAP for px, py in centers):
                        continue
                    centers.append((hx, hy))
                    break
            self.cov_c = np.asarray(centers, dtype=np.float64).reshape(-1, 2)
            self.cov_r = np.full(len(centers), R, dtype=np.float64)
            mask = np.zeros((self.gw, self.gw), dtype=bool)
            for (px, py), rad in zip(self.cov_c, self.cov_r):
                mask |= (self._cell_x - px) ** 2 + (self._cell_y - py) ** 2 <= rad * rad   # v1 `_build_world` 과 같은 셀 중심 식
            self.cover_cell = mask
            self.cover_frac_actual = float(mask.mean())
            self.regen_field = cfg.food_regen_base * self.food_regen_mult * np.where(
                self.cover_cell, cfg.food_cover_regen_mult, 1.0
            )
        self.stage_complete = None
        if ist["start_layout"] == "stage":
            # C++ PlanStage: 늑대 먼저(모서리, 모자라면 무대 안 후보), 그다음 사슴(무대 균등 후보, 늑대·앞 사슴과 떨어진 것만). 후보마다 x, y
            g = self.feature_rng("integrated_stage", 0)
            room = c - ist["deer_margin"]
            wg2, dw2, sp2 = ist["wolf_gap"] ** 2, ist["deer_wolf_gap"] ** 2, ist["deer_spacing"] ** 2
            M, N = self.M, self.N
            wolves = np.zeros((0, 2))

            def far(p, pts, d2):
                return not len(pts) or bool((((pts - p) ** 2).sum(1) >= d2).all())

            corner = ist["wolf_corner_frac"] * size
            for sx, sy in IST_CORNERS:
                if len(wolves) >= M:
                    break
                h = np.array([c + sx * corner, c + sy * corner])
                if far(h, wolves, wg2):
                    wolves = np.vstack([wolves, h])
            for _ in range(IST_WOLF_TRIES):
                if len(wolves) >= M:
                    break
                h = c + g.uniform(-room, room, 2)
                if far(h, wolves, wg2):
                    wolves = np.vstack([wolves, h])
            deer = np.zeros((N, 2))
            n = 0
            tries = max(IST_DEER_TRIES_MIN, IST_DEER_TRIES_PER * N)
            for _ in range(tries):
                if n >= N:
                    break
                h = c + g.uniform(-room, room, 2)
                if far(h, wolves, dw2) and far(h, deer[:n], sp2):
                    deer[n] = h
                    n += 1
            self.pred_pos[:len(wolves)] = wolves          # 다 못 놓은 개체는 v1 자리 그대로(C++ bComplete 거짓)
            self.pos[:n] = deer[:n]
            self.stage_complete = bool(len(wolves) == M and n == N)
        if ist["head_layout"] == "golden":
            a = np.arange(self.N, dtype=np.float64) * IST_GOLDEN_ANGLE
            self.head = np.stack([np.cos(a), np.sin(a)], 1)
            b = (np.arange(self.M, dtype=np.float64) + IST_WOLF_HEAD_OFFSET) * IST_GOLDEN_ANGLE
            self.pred_head = np.stack([np.cos(b), np.sin(b)], 1)

    def _ist_wolf_kinds(self) -> None:
        """통합 무대 (o) wolf_kinds 'alternate': `_threats_reset` 바로 뒤에 v1 포식자 칸(0..M_base−1)을 짝수 = 잠행-돌진형, 홀수 = 근접 추격형으로
        덮는다. 모두 근접(원거리형 없음, 속력 herb_speed × pred_speed_mult, 포획 거리 pred_melee_catch_r)·주행성(pred_sleep 을 켰으면 야행성 없음).
        threats·pred_sleep 스트림 뽑기는 이미 끝났다(규칙 2). v1 원거리형 배치(_pred_ranged_v1)는 v1 스트림 호출 모양을 정하므로 그대로 둔다.
        C++ 꼴: Spec = (Ordinal % 2 == 0) ? MakeStalkerSpec(PredSpeedMult, false) : MakeChaserSpec(PredSpeedMult, false, false)."""
        cfg, Mb = self.cfg, self.M_base
        stalker = (np.arange(Mb) % 2) == 0
        self.pred_type[:Mb] = np.where(stalker, PT_STALKER, PT_CHASER)
        self.pred_ranged[:Mb] = False
        self.pred_speed[:Mb] = cfg.herb_speed * self.pred_speed_mult
        self.pred_catch_r[:Mb] = cfg.pred_melee_catch_r
        self.pred_is_player = self.pred_type == PT_PLAYER
        self.threat_p_stalk = float(stalker.mean()) if Mb else 0.0
        if self._ps is not None:
            self.pred_nocturnal[:Mb] = False

    def _cover_overlap_cells(self) -> np.ndarray:
        """은신처 원과 조금이라도 겹치는 셀 (gw,gw) bool — v3 현실성 (e) 의 '은신처 셀'. 셀 (iy, ix) 의 닫힌 사각형
        [ix·c, (ix+1)·c] × [iy·c, (iy+1)·c] (c = food_cell, 반올림 여유 EPS 만큼 넓힘)에서 원 중심에 가장 가까운 점이 원 안이면(거리 식은
        `_in_cover` 와 같은 √(dx² + dy²) − r ≤ 0) 겹친다. 원 안의 위치는 `_cell_index` 가 고르는 셀이 늘 이 마스크 안이다 — 안전한
        자리(원 안)가 먹이가 줄지 않은 셀 위에 남지 않는다. v1 의 cover_cell(셀 중심이 원 안)을 포함한다. 난수를 쓰지 않는다.
        C++ 꼴(셀 하나, 원 k 마다): FVector2D Q(FMath::Clamp(C.X, X0 - EPS, X0 + Cell + EPS), FMath::Clamp(C.Y, Y0 - EPS, Y0 + Cell + EPS));
          bOverlap |= FVector2D::Distance(Q, C) - R <= 0;"""
        c = float(self.cfg.food_cell)
        lo = np.arange(self.gw, dtype=np.float64) * c
        x0, y0 = np.meshgrid(lo - EPS, lo - EPS)              # (gw,gw), [iy, ix] — _cell_x·_cell_y 와 같은 배치
        x1, y1 = x0 + (c + 2.0 * EPS), y0 + (c + 2.0 * EPS)
        out = self.cover_cell.copy()
        for (cx, cy), r in zip(self.cov_c, self.cov_r):
            qx = np.clip(cx, x0, x1) - cx
            qy = np.clip(cy, y0, y1) - cy
            out |= np.sqrt(qx * qx + qy * qy) - r <= 0.0
        return out

    def _rz_cover_food_apply(self) -> None:
        """v3 현실성 (e) 은신처 먹이 부족 (모듈 docstring (e)). `_build_world` 직후, `_food_v_reset` 전에 부른다. 난수를 쓰지 않는다.
        은신처 셀(훅 cover_food_cell = `_cover_overlap_cells`, 은신처 원과 겹치는 셀)의 용량 cap0 ← cap_frac × cap0, 먹이 F ← min(F, cap0)
        (= 새 cap0), 재생률 ← food_regen_base × food_regen_mult × regen_frac(v1 의 × food_cover_regen_mult 대신). 밖 셀은 v1 그대로다.
        통계 food_cap_kept = 새 용량 합 / v1 용량 합(용량이 없는 세계는 1). C++ 꼴(셀 하나):
          if (bCoverFoodCell) { Cap0 *= CapFrac; Food = FMath::Min(Food, Cap0); Regen = RegenBase * RegenMult * RegenFrac; }
        v3 R3 (e′, 선택 키 frac_range): CapFrac = RegenFrac = f = 하 + (상 − 하)·u, u = 자기 스트림 part 0 의 첫 난수(세계마다 하나).
        언리얼은 학습 범위 안의 한 값을 설정으로 둔다(배치 난수는 옮기지 않는다). 훅 cover_food_cap·cover_food_regen = 이 세계의 배수."""
        self.cover_food_cell = self._cover_overlap_cells()
        cfg, zf, cell = self.cfg, self._zf, self.cover_food_cell
        if zf["frac_range"] is not None:
            lo, hi = zf["frac_range"]
            u = float(self.feature_rng("realism_cover_food", 0).random())
            cap = regen = lo + (hi - lo) * u
        else:
            cap, regen = zf["cap_frac"], zf["regen_frac"]
        self.cover_food_cap, self.cover_food_regen = cap, regen
        v1_sum = float(self.food_cap.sum())
        self.food_cap = np.where(cell, self.food_cap * cap, self.food_cap)
        np.minimum(self.food, self.food_cap, out=self.food)
        self.regen_field = cfg.food_regen_base * self.food_regen_mult * np.where(cell, regen, 1.0)
        self._zf_kept = float(self.food_cap.sum()) / v1_sum if v1_sum > 0.0 else 1.0

    # ------------------------------------------------------------------ #
    # v3 R3 세계 (모듈 docstring 'R3 세계')
    # ------------------------------------------------------------------ #

    def _rz_terrain_reset(self) -> None:
        """v3 R3 (h) 지형 격자 (모듈 docstring (h) '만드는 법'). `_build_world` 뒤에 부른다. 자기 스트림 part 0·1·2 만 쓴다 — 은신처·먹이·
        v1 스트림과 독립이다. 훅: terrain_cell (gw, gw) int8 {0 보통, 1 눈, 2 거친 땅}, terrain_patches (P, 4) [땅, x, y, r](놓은 순서 —
        골든·장면용 자료), snow_target·rough_target(넓이 목표), snow_frac_actual·rough_frac_actual(실제 셀 비율)."""
        zt = self._zt
        u = self.feature_rng("realism_terrain", 0).random(4)
        (s_lo, s_hi), (r_lo, r_hi) = zt["snow_frac"], zt["rough_frac"]
        s_t = 0.0 if u[0] < zt["zero_p"][0] else s_lo + (s_hi - s_lo) * float(u[1])
        r_t = 0.0 if u[2] < zt["zero_p"][1] else r_lo + (r_hi - r_lo) * float(u[3])
        patches = []

        def paint(target, part, kind, free):
            # free: 칠할 수 있는 셀(거친 땅은 눈이 아닌 셀). 넓이는 칠한 셀 & free 로 잰다
            g = self.feature_rng("realism_terrain", part)
            mask = np.zeros((self.gw, self.gw), dtype=bool)
            for _ in range(zt["max_patches"]):
                if (mask & free).mean() >= target:
                    break
                c = g.uniform(0.0, self.size, 2)
                rad = float(g.uniform(zt["patch_r"][0], zt["patch_r"][1]))
                patches.append((float(kind), float(c[0]), float(c[1]), rad))
                mask |= (self._cell_x - c[0]) ** 2 + (self._cell_y - c[1]) ** 2 <= rad * rad
            return mask & free

        everywhere = np.ones((self.gw, self.gw), dtype=bool)
        snow = paint(s_t, 1, TERRAIN_SNOW, everywhere)
        rough = paint(r_t, 2, TERRAIN_ROUGH, ~snow)
        self.terrain_cell = np.where(snow, TERRAIN_SNOW, np.where(rough, TERRAIN_ROUGH, TERRAIN_NORMAL)).astype(np.int8)
        self.terrain_patches = np.asarray(patches, dtype=np.float64).reshape(-1, 4)
        self.snow_target, self.rough_target = s_t, r_t
        self.snow_frac_actual, self.rough_frac_actual = float(snow.mean()), float(rough.mean())

    def _rz_terrain_of(self, p: np.ndarray) -> np.ndarray:
        """위치 p (n,2) 의 땅 번호 (n,) int8 — 먹이와 같은 셀 색인(`_cell_index`)."""
        ix, iy = self._cell_index(p)
        return self.terrain_cell[iy, ix]

    def _rz_wall_r(self) -> np.ndarray:
        """막는 위협이 보는 은신처 원 반지름 (K,) = r_k + wolf_margin (모듈 docstring (c″)). 여유 0 이면 r_k + 0 = r_k 그대로(비트 동일)."""
        return self.cov_r + self._zw_m

    def _rz_inside_disc(self, q: np.ndarray) -> np.ndarray:
        """위치 q (n,2) 가 막는 위협에게 어느 은신처 원 안인가(|q − c| < r + wolf_margin, 둘레 위는 밖) (n,) bool — v3 R3 (c′)·(c″) 늑대
        진입 금지의 판정. 사슴의 안전 판정 `_in_cover`(|q − c| − r ≤ 0, 여유 없음)와 달리 둘레를 밖으로 둔다(밀어낸 위치는 r + wolf_margin +
        WALL_EPS 다)."""
        if not len(self.cov_r) or not len(q):
            return np.zeros(len(q), dtype=bool)
        dx = q[:, 0:1] - self.cov_c[:, 0][None, :]
        dy = q[:, 1:2] - self.cov_c[:, 1][None, :]
        return (np.sqrt(dx * dx + dy * dy) < self._rz_wall_r()[None, :]).any(1)

    def _rz_wall_reset(self) -> None:
        """v3 R3 (c′) reset: 막는 위협(_zw_sel — 포식자 전부, realism_shelter.player_too 면 플레이어형 위협도)을 정하고, 은신처 원 안에
        놓인 막는 위협을 가장 가까운 후보로 옮긴다. 후보 = 원마다 (그 원 중심 → 위협 쪽 반지름 방향의 둘레 밖 점) 하나와 WALL_RING
        방향의 둘레 밖 점(반지름 r + wolf_margin + WALL_EPS, (c″)) 가운데 맵 [0, size]² 안이고 모든 원 밖인 점, 거리가 같으면 앞 후보. 난수를
        쓰지 않는다(v1 배치 난수는 그대로, features.py 규칙 2). 옮긴 수는 wall_reset_n. 후보가 없으면(맵이 원으로 덮인 경우) 그대로 두고 센다."""
        player = self.pred_is_player if self._th is not None else np.zeros(self.M, dtype=bool)
        self._zw_sel = ~player | self._zs["player_too"]
        self._zw_reset_moved = 0
        self._zw_reset_failed = 0
        if not len(self.cov_r) or not self.M:
            return
        inside = self._zw_sel & self._rz_inside_disc(self.pred_pos)
        ang = 2.0 * np.pi * np.arange(WALL_RING) / WALL_RING
        ring = np.stack([np.cos(ang), np.sin(ang)], 1)
        for m in np.flatnonzero(inside):
            p = self.pred_pos[m]
            cand = []
            for c, r in zip(self.cov_c, self._rz_wall_r()):
                v = p - c
                n = float(np.sqrt(v @ v))
                u = v / n if n > EPS else np.array([1.0, 0.0])
                rr = r + WALL_EPS
                cand.append((c + rr * u)[None, :])
                cand.append(c[None, :] + rr * ring)
            C = np.concatenate(cand)
            ok = (C >= 0.0).all(1) & (C <= self.size).all(1) & ~self._rz_inside_disc(C)
            if not ok.any():
                self._zw_reset_failed += 1
                continue
            d2 = ((C - p) ** 2).sum(1)
            self.pred_pos[m] = C[int(np.argmin(np.where(ok, d2, np.inf)))]
            self._zw_reset_moved += 1

    def _rz_wall_push(self, q: np.ndarray, p: np.ndarray, sel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """v3 R3 (c′) 밀어내기 (모듈 docstring (c′)·(c″)): 막는 위협(sel)의 이동 뒤 위치 q 가 은신처 원 k 안(반지름 R_k = r_k + wolf_margin)이면
        c_k + (R_k + WALL_EPS)·단위(q − c_k) (q 가 중심과 겹치면 단위(p − c_k), p = 이동 전 위치)로 옮긴다. 원 순서대로, 원 안인 위협이 없을
        때까지 최대 WALL_PASSES 바퀴.
        반환 (새 q, 밀어낸 위협). 그래도 원 안인 위협은 부르는 쪽이 벽 반사·clip 뒤에 이전 위치로 되돌린다."""
        q = q.copy()
        pushed = np.zeros(len(q), dtype=bool)
        if not len(self.cov_r) or not sel.any() or not (sel & self._rz_inside_disc(q)).any():
            return q, pushed            # 대부분의 스텝: 원 안인 막는 위협이 없다(원마다 도는 아래 판정과 같은 식이라 결과가 같다)
        radii = self._rz_wall_r()
        for _ in range(WALL_PASSES):
            moved = False
            for c, r in zip(self.cov_c, radii):
                ex, ey = q[:, 0] - c[0], q[:, 1] - c[1]
                d = np.sqrt(ex * ex + ey * ey)
                inside = sel & (d < r)
                if not inside.any():
                    continue
                px, py = p[:, 0] - c[0], p[:, 1] - c[1]
                dp = np.sqrt(px * px + py * py)
                far = d > EPS
                ux = np.where(far, ex / np.maximum(d, EPS), px / np.maximum(dp, EPS))
                uy = np.where(far, ey / np.maximum(d, EPS), py / np.maximum(dp, EPS))
                rr = r + WALL_EPS
                q[inside, 0] = c[0] + rr * ux[inside]
                q[inside, 1] = c[1] + rr * uy[inside]
                pushed |= inside
                moved = True
            if not moved:
                break
        return q, pushed

    def _rz_wall_tangent(self, p: np.ndarray, v: np.ndarray) -> np.ndarray:
        """v3 R3 (c′) 되돌림 전 접선 미끄러짐 (모듈 docstring (c′)·(c″)): 이전 위치 p (n,2)(원 밖)에서 둘레가 가장 가까운 원 k(|p − c_k| − R_k 가
        가장 작은 것, R_k = r_k + wolf_margin, 같으면 낮은 번호)의 바깥 법선 n = 단위(p − c_k)에 대해 이동 v (n,2)의 안쪽 성분만 뺀다: v′ = v − min(v·n, 0)·n.
        반환 clip(p + v′, 0, size). p 가 둘레 위면 접선은 원 밖이라 그 원에는 들어가지 않는다(다른 원·맵 가장자리는 부르는 쪽이 본다).
        C++ 꼴: int K = NearestEdge(P); FVector2D N = SafeDir(P - C[K], FVector2D(1, 0));
          FVector2D Vt = V - FMath::Min(V | N, 0.f) * N;  Q = Clamp(P + Vt, 0, Size);"""
        ex = p[:, 0:1] - self.cov_c[:, 0][None, :]
        ey = p[:, 1:2] - self.cov_c[:, 1][None, :]
        d = np.sqrt(ex * ex + ey * ey)
        k = (d - self._rz_wall_r()[None, :]).argmin(1)
        ar = np.arange(len(p))
        dk = d[ar, k]
        far = dk > EPS
        nx = np.where(far, ex[ar, k] / np.maximum(dk, EPS), 1.0)
        ny = np.where(far, ey[ar, k] / np.maximum(dk, EPS), 0.0)
        vn = np.minimum(v[:, 0] * nx + v[:, 1] * ny, 0.0)
        q = np.stack([p[:, 0] + (v[:, 0] - vn * nx), p[:, 1] + (v[:, 1] - vn * ny)], 1)
        return np.clip(q, 0.0, self.size)

    def _rz_chase_reset(self) -> None:
        """v3 R3 (f) 위협별 추격 고정 상태 (크기 M — 플레이어 칸 포함). `_threats_reset` 뒤에 부른다. 난수를 쓰지 않는다.
        chase_tgt: 고정한 사슴 슬롯(−1 = 없음, 스텝 끝 훅 — 언리얼 LockedPrey), chase_lost: 표적이 시야 밖인 연속 포식자 스텝,
        chase_pt: 마지막으로 본 표적 위치."""
        M = self.M
        self.chase_tgt = np.full(M, -1, dtype=np.int64)
        self.chase_lost = np.zeros(M, dtype=np.int64)
        self.chase_pt = np.zeros((M, 2))

    def _rz_chase_hold(self, hunting: np.ndarray) -> np.ndarray:
        """v3 R3 (f) 고정을 쥘 수 있는 위협 (M,) bool (모듈 docstring (f)): 사냥 중이고 추격형이거나, 잠행형이 돌진(stalk_phase 면 배회 —
        잠행 접근 — 도)이거나, player_too 면 플레이어형 위협이 돌진(stalk_phase 면 잠행) 모드다. 지금 상태(stalk_state·player_mode)로 본다."""
        zc = self._zc
        hold = np.asarray(hunting, dtype=bool).copy()
        if self._th is not None:
            st, md = self.stalk_state, self.player_mode
            stalker = self.pred_type == PT_STALKER
            ok_st = (st == ST_POUNCE) | (zc["stalk_phase"] & (st == ST_ROAM))
            ok_pl = zc["player_too"] & ((md == PM_CHARGE) | (zc["stalk_phase"] & (md == PM_STALK)))
            hold &= np.where(stalker, ok_st, np.where(self.pred_is_player, ok_pl, True))
        return hold

    def _rz_chase_release(self, dist: np.ndarray, dx: np.ndarray, dy: np.ndarray, inv: np.ndarray, in_cov: np.ndarray,
                          hunting: np.ndarray) -> None:
        """v3 R3 (f) 1) 놓기·시야 갱신 (모듈 docstring (f)). `_step_predators_v3` 가 사냥 가능을 정한 뒤, 표적 고르기 전에 부른다.
        거리·위치는 초식 이동 뒤·포식자 이동 전 값이다(표적 고르기와 같다)."""
        lk = self.chase_tgt
        has = lk >= 0
        if not has.any():
            return
        M = self.M
        ar = np.arange(M)
        k = np.where(has, lk, 0)
        hold = self._rz_chase_hold(hunting)
        fov = (dx[ar, k] * self.pred_head[:, 0] + dy[ar, k] * self.pred_head[:, 1]) * inv[ar, k] >= self.cfg.pred_fov_cos
        sight = (dist[ar, k] <= self.cfg.pred_view_r) & fov
        if self._th is not None:
            sight |= self.pred_is_player                    # 플레이어형 위협은 맵 전체를 본다
        rel_state = has & ~hold
        rel_cover = has & hold & in_cov[k]
        keep = has & hold & ~in_cov[k]
        seen, lost = keep & sight, keep & ~sight
        self.chase_lost[seen] = 0
        self.chase_pt[seen] = self.pos[k[seen]]
        self.chase_lost[lost] += 1
        rel_lost = lost & (self.chase_lost > self._zc["lost_steps"])
        rel = rel_state | rel_cover | rel_lost
        lk[rel] = -1
        self.chase_lost[rel] = 0
        self._zc_rel_state += int(np.count_nonzero(rel_state))
        self._zc_rel_cover += int(np.count_nonzero(rel_cover))
        self._zc_rel_lost += int(np.count_nonzero(rel_lost))

    def _rz_chase_target(self, j, d_t, has_target, dist):
        """v3 R3 (f) 3) 고정한 표적으로 덮기: 쥔 위협은 j = 고정 표적, 보이면 d_t = 실거리, 안 보이면 d_t = ∞(돌진을 새로 시작하지 않는다),
        has_target = 참. 반환 (j, d_t, has_target, 안 보이는 고정 — 마지막으로 본 자리로 간다)."""
        lk = self.chase_tgt
        held = lk >= 0
        lost = held & (self.chase_lost > 0)
        if held.any():
            ar = np.arange(self.M)
            kk = np.where(held, lk, 0)
            j = np.where(held, kk, j)
            d_t = np.where(held & ~lost, dist[ar, kk], np.where(held, np.inf, d_t))
            has_target = has_target | held
            self._zc_held += int(np.count_nonzero(held))
            self._zc_lost += int(np.count_nonzero(lost))
        return j, d_t, has_target, lost

    def _rz_chase_acquire(self, j: np.ndarray, has_target: np.ndarray, hunting: np.ndarray) -> None:
        """v3 R3 (f) 4) 새 고정: 잠행형·플레이어 상태 전이(`_threat_motion`) 뒤, 쥘 수 있는 위협(전이 뒤 상태)이 고정이 없고 표적이 있으면
        그 표적(j)을 고정한다(돌진을 막 시작한 잠행형은 돌진 표적을 고정한다)."""
        new = self._rz_chase_hold(hunting) & (self.chase_tgt < 0) & has_target
        if new.any():
            self.chase_tgt[new] = j[new]
            self.chase_lost[new] = 0
            self.chase_pt[new] = self.pos[j[new]]
            self._zc_lock_n += int(np.count_nonzero(new))

    def _food_v_reset(self) -> None:
        """v2.0b 세계 생성 (계획서 4.9.1). v1 세계(`_build_world`)를 다 만든 뒤 부른다.

        food_v 스트림 part 0 에서 난수 정확히 3개를 이 순서로 뽑는다. 목록 길이와 상관없이 소비가 같다
        (`integers(1)` 은 난수를 소비하지 않으므로 고르기에 쓰지 않는다).
          1) u ~ U[0,1) → 회복 반감기 h = recovery_half_lives[floor(u·n)], ρ = 1 − 2^(−1/h)
          2) 왼쪽 절반 V 초기 비율 ~ U[init_frac]   3) 오른쪽 절반 ~ U[init_frac]
        V = cap0 × (그 셀이 속한 절반의 비율), F = min(v1 초기값 cap0, V). cap0 = 0 셀은 F = V = 0 이다.
        """
        fv, g = self._fv, self.feature_rng("food_v", 0)
        hl = fv["half_lives"]
        h = hl[min(int(g.random() * len(hl)), len(hl) - 1)]
        frac = g.uniform(fv["init_frac"][0], fv["init_frac"][1], 2)       # [왼쪽, 오른쪽]
        self.food_v_half_life = h
        self.food_v_rho = 1.0 - 2.0 ** (-1.0 / h)
        self.food_v_init = (float(frac[0]), float(frac[1]))
        self.food_v = self.food_cap * np.where(self._left_half(), frac[0], frac[1])
        self._fv_floor = fv["floor"] * self.food_cap
        np.minimum(self.food, self.food_v, out=self.food)
        # 기록 (food_stats·food_cells): reset 뒤 셀별 누적 섭취, 마지막으로 뜯긴 스텝(self.t, 없으면 −1)
        self._fv_eaten = np.zeros_like(self.food_cap)
        self._fv_last_eat = np.full(self.food_cap.shape, -1, dtype=np.int64)

    def _daynight_reset(self) -> None:
        """v2.4 세계 생성 (계획서 4.9.2·4.7). v1 세계(`_build_world`, t = 0)를 다 만든 뒤 부른다.

        daynight 스트림에서만 뽑는다(`daynight_draws`): part 0 에서 정확히 3개(낮 고정, T, o — 낮 고정 세계도 같은
        수를 뽑는다), start_induce > 0 이면 part 2 에서 1 + N 개. 유도된 세계는 해 지기 0.1·T 스텝 전에 시작하고
        초식 에너지가 U[0.2, 0.5]·max_energy 다. 그 뒤 t = 0 의 어둠·관측 값을 정한다(`_daynight_update`).
        """
        dn = self._dn
        dr = daynight_draws(dn, self.seed, self.N)
        self.dn_period, self.dn_offset = dr["period"], dr["offset"]
        self.dn_tw, self.day_fixed, self.dn_induced = dr["tw_steps"], dr["day_fixed"], dr["induced"]
        if dr["induced"]:
            self.energy = dr["energy"] * self.cfg.max_energy
        if self._ist is not None and self._ist["day_offset"] is not None:
            # 통합 무대 (m): 팀 시계와 같은 시작 위상(언리얼 DayOffset 0 — t = 0 이 새벽 전환). 뽑기 3개는 위에서 그대로 했다(규칙 2).
            # 첫 _daynight_update(아래)가 이 위상으로 어둠과 realism_night 의 시작 상태를 정한다
            self.dn_offset = self._ist["day_offset"] % self.dn_period
        self._daynight_update()

    def _pred_sleep_reset(self) -> None:
        """v2.4s 세계 생성. pred_sleep 스트림 part 0 에서 1 + M 개: q ~ U[nocturnal_frac], 포식자마다 u < q 면 야행성.
        포식자 배치(`_build_world`)를 만든 뒤, 어둠을 정하는 `_daynight_reset` 전에 부른다."""
        g = self.feature_rng("pred_sleep", 0)
        lo, hi = self._ps["nocturnal_frac"]
        q = float(g.uniform(lo, hi))
        u = g.random(self.M)
        self.pred_noct_frac = q
        self.pred_nocturnal = u < q
        self.pred_asleep = np.zeros(self.M, dtype=bool)
        self._pred_speed_mult = np.ones(self.M)
        self._ps_asleep_sum, self._ps_steps = 0.0, 0

    def _threats_reset(self) -> None:
        """v3 R0 위협 유형 (명세 3절 M3·플레이어형 위협). 포식자 배치·밤잠 배치 뒤, `_daynight_reset` 전에 부른다.

        threats 스트림에서만 뽑는다:
          part 0 에서 1 + M 개: p_stalk ~ U[stalk_frac], 포식자마다 u < p_stalk 면 잠행-돌진형. 잠행형은 근접형이다 —
                  v1 이 뽑은 원거리형 배치를 덮고(v1 뽑기는 그대로, features.py 규칙 2) 속력·포획 거리를 근접형으로 둔다
          part 1 에서 4 개(늘): u < player_frac 면 플레이어가 있다, 위치 (x, y)·size, heading 각 2π·u
          part 2: 플레이어 모드를 새로 고를 때마다 2 개(`_player_new_mode`), part 3: 배회 선회(스텝마다 1 개)
        플레이어는 포식자 칸 끝(색인 M_base)에 붙는다. 밤잠 배열에는 야행성으로 넣어 잠도 박명 감속도 받지 않는다(밤에 자지 않는다).
        """
        cfg, th, Mb = self.cfg, self._th, self.M_base
        g0 = self.feature_rng("threats", 0)
        self.threat_p_stalk = float(g0.uniform(th["stalk_frac"][0], th["stalk_frac"][1]))
        stalker = g0.random(Mb) < self.threat_p_stalk
        self.pred_type = np.where(stalker, PT_STALKER, PT_CHASER).astype(np.int8)
        self.pred_ranged = self.pred_ranged & ~stalker
        base = cfg.herb_speed * self.pred_speed_mult
        self.pred_speed = np.where(self.pred_ranged, base * cfg.pred_ranged_speed_mult, base)
        self.pred_catch_r = np.where(self.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r)
        u = self.feature_rng("threats", 1).random(4)
        self.player_present = bool(u[0] < th["player_frac"])
        if self.player_present:
            ang = 2.0 * np.pi * u[3]
            self.pred_pos = np.vstack([self.pred_pos, [u[1] * self.size, u[2] * self.size]])
            self.pred_head = np.vstack([self.pred_head, [math.cos(ang), math.sin(ang)]])
            self.pred_ranged = np.append(self.pred_ranged, False)
            self._pred_ranged_v1 = np.append(self._pred_ranged_v1, False)
            self.pred_speed = np.append(self.pred_speed, 0.0)       # 플레이어 속력은 모드가 정한다
            self.pred_catch_r = np.append(self.pred_catch_r, th["player_catch_r"])
            self.pred_cd = np.append(self.pred_cd, 0).astype(np.int32)
            self.pred_type = np.append(self.pred_type, PT_PLAYER).astype(np.int8)
            if self._ps is not None:
                self.pred_nocturnal = np.append(self.pred_nocturnal, True)
                self.pred_asleep = np.append(self.pred_asleep, False)
                self._pred_speed_mult = np.append(self._pred_speed_mult, 1.0)
            self.M = Mb + 1
        self.pred_is_player = self.pred_type == PT_PLAYER
        self.stalk_state = np.zeros(self.M, dtype=np.int8)
        self.stalk_left = np.zeros(self.M, dtype=np.int64)
        self.player_mode = np.zeros(self.M, dtype=np.int8)
        self.player_left = np.zeros(self.M, dtype=np.int64)
        if self.player_present:
            self._player_new_mode(Mb)

    def _player_new_mode(self, i: int) -> None:
        """플레이어 모드를 새로 고른다(part 2 에서 2 개): u0 < player_stalk_p 면 잠행 접근, 아니면 배회. 길이 =
        하 + ⌊u1·(상 − 하 + 1)⌋ 스텝(상에서 자른다)."""
        th = self._th
        u = self.feature_rng("threats", 2).random(2)
        lo, hi = th["player_mode_steps"]
        self.player_mode[i] = PM_STALK if u[0] < th["player_stalk_p"] else PM_WANDER
        self.player_left[i] = min(lo + int(u[1] * (hi - lo + 1)), hi)

    def _stare_reset(self) -> None:
        """v3 R2 M7 위협별 상태 (명세 2-6, 크기 M — 플레이어 칸 포함). `_threats_reset` 뒤에 부른다. 난수를 쓰지 않는다.
        pred_lock: 잠근 초식 슬롯(−1 = 없음), spot_cnt: 이어서 노려본 스텝(대치·들킴을 세는 중), balk_dir: 물러남 방향(단위),
        spotted_left: 플레이어 '들킴' 남은 스텝, spotted_charge: 지금 돌진이 들킨 돌진인가. 물러남 남은 스텝은 stalk_left 를 쓴다.
        스텝 뒤 훅 stare_by (N,): 이번 스텝에 나를 잠근 위협이 노려보기 S 로 대치·들킴을 세는 중이면 그 위협 색인(여럿이면 낮은
        번호), 아니면 −1."""
        M = self.M
        self.pred_lock = np.full(M, -1, dtype=np.int64)
        self.spot_cnt = np.zeros(M, dtype=np.int64)
        self.balk_dir = np.zeros((M, 2))
        self.spotted_left = np.zeros(M, dtype=np.int64)
        self.spotted_charge = np.zeros(M, dtype=bool)
        self.stare_by = np.full(self.N, -1, dtype=np.int64)

    def _alarm_reset(self) -> None:
        """v3 R2 M8 스텝 뒤 훅과 방출 버퍼 (명세 3-7). 개체 경보 상태는 RepState 의 경보 칸이다(`repertoire.alarm_state`).
        alarm_level = 관측 alarm_heard 값(E′ 뒤, 리스폰 전), alarm_hop(쥔 경보의 홉, 없으면 −1), alarm_seq, alarm_pt,
        alarm_emit(이번 스텝 방출 홉, 없으면 −1), entry_cause, alarm_e7(이번 스텝 사건 E7), alarm_from(이번 스텝에 받아들인
        경보의 방출원 슬롯, 없으면 −1 — 리플레이·확인표용). 리스폰은 훅을 바꾸지 않는다."""
        N = self.N
        self.alarm_level = np.zeros(N)
        self.alarm_hop = np.full(N, -1, dtype=np.int64)
        self.alarm_seq = np.zeros(N, dtype=np.int64)
        self.alarm_pt = np.zeros((N, 2))
        self.alarm_emit = np.full(N, -1, dtype=np.int64)
        self.entry_cause = np.zeros(N, dtype=np.int64)
        self.alarm_e7 = np.zeros(N, dtype=bool)
        self.alarm_from = np.full(N, -1, dtype=np.int64)
        self._al_em = None                                        # 이번 스텝 방출 목록 (A′ 에서 만들고 E′ 에서 쓴다)
        self._pred_active = np.zeros(self.M, dtype=bool)          # 직전 포식자 스텝에 사냥 중(헛경보 통계 전용)

    def _repertoire_reset(self) -> None:
        """v3 R0 행동 상태 (env_v2/repertoire.py). 어둠을 정한 뒤(`_daynight_reset`) 부른다. 모든 개체가 GRAZE 진입이다."""
        rp, N = self._rp, self.N
        self._rep_gen = np.zeros(N, dtype=np.int64)               # 슬롯별 세대(리스폰 횟수) — 사건 결정 지연의 개체 키
        self._rs = rep.RepState(N, rp, self.energy / self.cfg.max_energy, self.dark, self.seed,
                                alarm=self._al is not None)       # v3 R2: alarm 세계만 경보 칸(repertoire.alarm_state)
        self._rep_see = np.full(N, rp["graze_head_down"])         # 자기 포식자 탐지 반경 배수 (다음 관측)
        self._rep_see_last = self._rep_see.copy()                 # 직전 관측의 배수 (사건 비교 시야, `_geometry`)
        self._rep_still = np.zeros(N, dtype=bool)                 # M1 정지 (이번 스텝)
        self._rep_crouch = np.zeros(N, dtype=bool)                # 웅크림(도착 HIDE, 이번 스텝) — M7 추적 가능 판정
        self._rep_cover = np.ones(N)                              # 은신처 안일 때의 은신 배수 (이번 스텝)
        self._rep_eat = np.zeros(N)                               # 섭식·대사 배수 (이번 스텝, 제어기)
        self._rep_drain = np.ones(N)
        self._rep_a4 = np.zeros((N, ACT_DIM))                     # v1 stats() 의 행동 열 자리(레퍼토리 세계는 0)
        self._rep_export()

    def _rep_export(self) -> None:
        """스텝 뒤 훅 (애니메이션 계약, 언리얼이 받는 넷): 이번 스텝에 실행한 행동·위상·경과·seq 의 사본. 리스폰은 바꾸지
        않는다(죽은 슬롯의 마지막 프레임이 그 개체의 값이다, replay_v2 규약). 새 개체의 상태는 다음 스텝 값부터다."""
        rs = self._rs
        self.behavior = rs.behavior.copy()
        self.beh_phase = rs.phase.copy()
        self.beh_steps = rs.steps_in.copy()
        self.beh_seq = rs.seq.copy()

    def rep_obs_extra(self) -> np.ndarray:
        """v3 추가 관측 9칸 (N, 9) float32 — 지금 관측(스텝 끝 기하)과 같은 때의 값. obs_extra 가 false 여도 계산한다
        (R1 학습·손 규칙용). 순서는 `repertoire.OBS_EXTRA_NAMES`."""
        if self._rp is None:
            raise ValueError("rep_obs_extra 는 repertoire 를 켠 세계에만 있다")
        return rep.obs_extra(self._rs, self._rp, self._g)

    def _daynight_update(self) -> None:
        """지금 t 의 어둠 d·실효 탐지 반경·관측 두 칸 (계획서 4.9.2, 4.2). reset 과 `step` 의 t 증가 뒤에 부른다.

        여기서 정한 값을 그 뒤 관측(8)과 다음 스텝의 동역학(섭식·휴식 대사)이 함께 쓴다 — 결정 때 값이다.
        visibility = 1 − detect_night·d (날씨 w 는 v2.6, 지금 1), to_transition = min(r / transition_norm, 1).
        낮 고정 세계는 d = 0, 반경 see_r, 관측 1·1 (중립값, 계획서 4.2)이다.
        """
        dn = self._dn
        if self.day_fixed:
            d, tt = 0.0, 1.0
        else:
            d, r = daynight_phase(self.t, self.dn_period, self.dn_offset, self.dn_tw)
            tt = min(r / dn["transition_norm"], 1.0)
        self.dark = d
        self._vis = 1.0 - dn["detect_night"] * d
        self._to_tr = tt
        self._see_pred = self.cfg.see_r * self._vis
        if self._ps is not None:        # v2.4s: 주행성 포식자의 잠·박명 감속 (결정 때 어둠, 다음 스텝 포식자 이동에 쓴다)
            ps = self._ps
            diurnal = ~self.pred_nocturnal
            if self._zn is not None:    # v3 현실성 (d): 잠을 늑대별 상태로(사냥 중·사슴 근처면 안 잠, 늑대마다 다른 잠·기상, 기상 가속)
                self._rz_night_update(d, diurnal)
                return
            self.pred_asleep = diurnal & (d >= ps["sleep_dark"])
            slow = (1.0 - d) if ps["twilight_slow"] else 1.0
            self._pred_speed_mult = np.where(self.pred_asleep, 0.0, np.where(diurnal, slow, 1.0))

    def _rz_night_reset(self) -> None:
        """v3 현실성 (d) 늑대별 밤잠 상태 (크기 M — 플레이어 칸 포함, 플레이어는 야행성으로 들어 있어 쓰지 않는다). 난수를 쓰지 않는다.
        `_threats_reset` 뒤, `_daynight_reset` 전에 부른다(첫 `_daynight_update` 가 '이미 밤이면 자고 있음'으로 시작 상태를 정하고
        지연을 그 세계의 박명 폭 τ 로 정한다). 위협 수·낮밤 주기를 바꾸는 하네스는 바꾼 뒤 이것을 다시 부르고 `_daynight_update` 를 부른다.
          _zn_delay: 잠·기상 지연 δ_m (`night_delays`, 최대 ⌊spread·τ⌋ — 낮 고정 세계는 어둠이 없어 0)
          _zn_act: 활동도 a_m ∈ [0, R] (R = ramp_steps, 속력 배수 a/R), _zn_settle: 눕는 중,
          _zn_dark_k: 깨어 있는 채 어둠(d ≥ sleep_dark)인 업데이트 수(이어서), _zn_wait: 기상까지 남은 업데이트(−1 = 기다리지 않음),
          _zn_hunt: 지난 포식자 스텝에 사냥 중(`_step_predators_v3` 가 쓴다), _zn_fresh: 다음 `_daynight_update` 가 시작 상태를 정한다."""
        M, zn = self.M, self._zn
        self._zn_delay = np.zeros(M, dtype=np.int64)
        self._zn_act = np.full(M, zn["ramp_steps"], dtype=np.int64)
        self._zn_settle = np.zeros(M, dtype=bool)
        self._zn_dark_k = np.zeros(M, dtype=np.int64)
        self._zn_wait = np.full(M, -1, dtype=np.int64)
        self._zn_hunt = np.zeros(M, dtype=bool)
        self._zn_fresh = True

    def _rz_night_update(self, d: float, diurnal: np.ndarray) -> None:
        """v3 현실성 (d) 한 업데이트 (모듈 docstring (d)). `_daynight_update` 가 어둠 d 를 정한 뒤 부른다(reset, 스텝 끝 t + 1 뒤 —
        포식자 이동 뒤·리스폰 전 위치). 야행성·플레이어는 늘 깨어 있고 속력 배수 1 이다. 순서(C++ 로 옮길 때 지킨다, 주행성 늑대 m 하나,
        R = RampSteps, bDark = D >= SleepDark, bHunt = 지난 포식자 스텝의 사냥 중 — 표적 있음, 또는 잠행형의 돌진·대치 상태):
          시작(fresh): bAsleep = bDark; Act = bAsleep ? 0 : R; bSettle = false; DarkK = 0; Wait = -1.
          자고 있음:  if (bDark) Wait = -1; else { if (Wait < 0) Wait = Delay;
                        if (Wait == 0) { bAsleep = false; Wait = -1; Act = 0; } else --Wait; }     // 깨면 아래 '깨어 있음'을 탄다
          깨어 있음(이번 업데이트에 깬 늑대 포함):
                      DarkK = bDark ? DarkK + 1 : 0;
                      bNear = 실거리 SettleR 안에 사슴(모든 슬롯, 리스폰 전)       — bDark && (bSettle || DarkK > Delay) 일 때만 잰다
                      bCalm = bDark && !bHunt && !bNear;
                      if (bSettle && !bCalm) bSettle = false;                            // 사냥·사슴·새벽이면 다시 일어난다
                      else if (!bSettle && bCalm && DarkK > Delay) bSettle = true;       // 눕기 시작
                      if (bSettle) { --Act; if (Act <= 0) { Act = 0; bAsleep = true; bSettle = false; DarkK = 0; } }
                      else Act = FMath::Min(Act + 1, R);
          SpeedMult = bAsleep ? 0 : FMath::Max(bTwilightSlow ? 1 - D : 1, NightFloor) * (R > 0 ? (float)Act / R : 1)."""
        ps, zn = self._ps, self._zn
        R = zn["ramp_steps"]
        dark = d >= ps["sleep_dark"]
        if self._zn_fresh:
            tw = 0 if self.day_fixed else int(self.dn_tw)
            self._zn_delay = night_delays(self.seed, self.M, int(math.floor(zn["spread"] * tw)))
            self.pred_asleep = diurnal & dark
            self._zn_act[:] = np.where(self.pred_asleep, 0, R)
            self._zn_settle[:] = False
            self._zn_dark_k[:] = 0
            self._zn_wait[:] = -1
            self._zn_fresh = False
        else:
            asleep = self.pred_asleep.copy()
            act, settle = self._zn_act.copy(), self._zn_settle.copy()
            # 자고 있음
            sl = diurnal & asleep
            woke = np.zeros(self.M, dtype=bool)
            if dark:
                self._zn_wait[sl] = -1
            else:
                w = np.where(sl & (self._zn_wait < 0), self._zn_delay, self._zn_wait)
                woke = sl & (w == 0)
                w = np.where(sl & (w > 0), w - 1, w)
                w[woke] = -1
                self._zn_wait = w
                asleep[woke] = False
                act[woke] = 0
                self._zn_wake_n += int(np.count_nonzero(woke))
            # 깨어 있음
            awake = diurnal & ~asleep
            self._zn_dark_k = np.where(awake & dark, self._zn_dark_k + 1, 0)
            near = np.zeros(self.M, dtype=bool)
            if dark:
                cand = awake & (settle | (self._zn_dark_k > self._zn_delay))
                if cand.any() and self.N:
                    dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]
                    dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
                    close = np.sqrt(dx * dx + dy * dy) <= zn["settle_r"]
                    if self.alive is not None:
                        # 통합 무대 (k): 시체는 '사슴 근처'가 아니다. 이번 스텝에 죽은 개체는 아직 산 슬롯이다(C++ NightUpdate 의 W.Prey 와 같다)
                        close[:, ~self.alive] = False
                    near = cand & close.any(1)
            calm = dark & ~self._zn_hunt & ~near
            ready = awake & ~settle & dark & (self._zn_dark_k > self._zn_delay)
            abort = awake & settle & ~calm
            start = ready & calm
            settle = (settle & ~abort) | start
            down = awake & settle
            act = np.where(down, act - 1, np.where(awake, np.minimum(act + 1, R), act))
            onset = down & (act <= 0)
            act[onset] = 0
            asleep |= onset
            settle[onset] = False
            self._zn_dark_k[onset] = 0
            self._zn_act, self._zn_settle, self.pred_asleep = act, settle, asleep
            self._zn_settle_n += int(np.count_nonzero(start))
            self._zn_abort_n += int(np.count_nonzero(abort))
            self._zn_onset_n += int(np.count_nonzero(onset))
            self._zn_block_deer_n += int(np.count_nonzero(ready & ~self._zn_hunt & near))
            self._zn_block_hunt_n += int(np.count_nonzero(ready & self._zn_hunt))
            if dark:
                self._zn_dark_n += int(np.count_nonzero(diurnal))
                self._zn_dark_awake += int(np.count_nonzero(diurnal & ~asleep))
        base = max((1.0 - d) if ps["twilight_slow"] else 1.0, zn["night_floor"])
        level = self._zn_act / R if R > 0 else np.ones(self.M)
        self._pred_speed_mult = np.where(self.pred_asleep, 0.0, np.where(diurnal, base * level, 1.0))

    # ------------------------------------------------------------------ #
    # 기하 (관측과 조향이 공유한다)
    # ------------------------------------------------------------------ #

    def _smooth(self, arr: np.ndarray, br: int) -> np.ndarray:
        """반경 br 셀 박스 평균. SAT를 새로 만든다 (reset 시 1회용)."""
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(arr, 0), 1, out=sat[1:, 1:])
        return self._box_mean(sat, max(1, br))

    def _box_mean(self, sat: np.ndarray, br: int) -> np.ndarray:
        """SAT에서 반경 br 셀 정사각 평균. 경계는 잘린 창의 실제 면적으로 나눈다."""
        g = self.gw
        i = np.arange(g)
        r0, r1 = np.clip(i - br, 0, g), np.clip(i + br + 1, 0, g)
        c0, c1 = r0, r1  # 정방 격자라 행/열 인덱스가 같다
        box = (
            sat[np.ix_(r1, c1)] - sat[np.ix_(r0, c1)] - sat[np.ix_(r1, c0)] + sat[np.ix_(r0, c0)]
        )
        return box / ((r1 - r0)[:, None] * (c1 - c0)[None, :])

    def _food_fields(self) -> None:
        """먹이 밀도(관측용)와 기울기(조향용)를 격자 전체에 대해 한 번 계산한다.

        두 필드의 블러 반경이 **다르다**. 일부러 그렇게 뒀다:

        - `food_blur` (관측 idx0): 반경 `see_r`. §9.4의
          `IWorldFoodProvider::GetFoodDensity(Location, Radius)` 와 맞추기 위한 반경 평균이다
          (각도 제한 없음 — 언리얼 인터페이스가 반경만 받는다).
        - `_food_g*` (조향 `food_grad`): 반경 `food_grad_blur` 셀. see_r 블러(11×11셀)에서
          기울기를 뽑으면 한 셀을 먹어치워도 값이 0.8%밖에 안 변해서, 개체 전원이 초기
          고밀도 지점으로 몰린 뒤 같은 셀을 두고 경쟁한다. 측정 결과 `forage=1`이
          `forage=0`보다 **덜 먹었다**. 좁은 반경을 쓰면 국소 고갈이 기울기에 바로 잡혀
          비어버린 주변을 벗어나는 방향을 가리킨다.

        `food_grad` 는 관측이 아니라 §3.3의 기하 입력이므로 이 분리가 §3 계약을 건드리지
        않는다. 언리얼도 `GetFoodDensity` 와 `FoodGrad` 를 별도로 제공한다 (§9.4/§9.5).
        """
        cfg = self.cfg
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(self.food, 0), 1, out=sat[1:, 1:])
        self.food_blur = self._box_mean(sat, max(1, int(round(cfg.see_r / cfg.food_cell))))
        gy, gx = np.gradient(self._box_mean(sat, max(1, int(cfg.food_grad_blur))))
        self._food_gx, self._food_gy = gx, gy

    def _cover_edge(self, p: np.ndarray):
        """은신처 원까지의 (dx, dy, 가장자리까지 거리) — 전부 (n,K)."""
        dx = self.cov_c[:, 0][None, :] - p[:, 0:1]
        dy = self.cov_c[:, 1][None, :] - p[:, 1:2]
        return dx, dy, np.sqrt(dx * dx + dy * dy) - self.cov_r[None, :]

    def _in_cover(self, p: np.ndarray) -> np.ndarray:
        """위치 `p` (n,2)가 은신처 원 안인가. 관측과 포식자 판정이 같은 정의를 쓴다."""
        if not len(self.cov_r):
            return np.zeros(len(p), dtype=bool)
        return self._cover_edge(p)[2].min(1) <= 0.0

    def _cell_index(self, p: np.ndarray):
        """월드 좌표 → 격자 인덱스 (ix=열, iy=행)."""
        k = 1.0 / self.cfg.food_cell
        ix = np.clip((p[:, 0] * k).astype(np.int32), 0, self.gw - 1)
        iy = np.clip((p[:, 1] * k).astype(np.int32), 0, self.gw - 1)
        return ix, iy

    def _geometry(self, idx: np.ndarray | None = None, out: dict | None = None) -> dict:
        """행 `idx` (None이면 전체)의 기하 정보를 계산한다.

        `out` 을 주면 그 딕셔너리의 해당 행만 덮어쓴다 (§4.5 `_observe_subset` 경로).
        """
        cfg = self.cfg
        if idx is None:
            idx = np.arange(self.N)
            self._food_fields()
        P = self.pos[idx]
        Hd = self.head[idx]
        n = len(idx)
        ar = np.arange(n)
        hx, hy = Hd[:, 0:1], Hd[:, 1:2]
        # 시야각 판정 문턱 cos(FOV/2). v2.2: 직전 스텝에 경계한 개체(self._wide)는 경계 시야(360° 면 −inf, 각도 판정
        # 없음)로 동족·포식자를 본다 — 관측 1·2·3 과 조향 기하(to_centroid·away_from_pred·d_pred_min)가 함께 넓어진다.
        # 반경은 see_r 그대로다(#5). vigilance 를 끈 세계는 v1 과 같은 스칼라 비교다.
        fov_cos = (cfg.fov_cos if self._vg is None else
                   np.where(self._wide[idx], self._vg["wide_cos"], cfg.fov_cos)[:, None])

        # 쌍별 계산은 전부 (n, ·) 2D로 둔다. (n,N,2) 3D 임시배열을 만들면 스텝의 75%를
        # 여기서 쓴다 (측정). 합산은 행렬곱으로 내려보낸다.

        # --- 동족: 시야(거리 + 각도) 내, 자기 제외 (§3.1 idx3) ---
        dx = self.pos[:, 0][None, :] - P[:, 0:1]
        dy = self.pos[:, 1][None, :] - P[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        # v3 현실성 (a): 동족 시야각은 kin_fov_deg(120 이면 cfg.fov_cos 그대로 — 같은 판정), 위협 시야각은 threat_fov_deg (아래 pvis)
        kin_cos = fov_cos if self._zv is None else self._zv["kin_cos"]
        kin_vis = (dist <= cfg.see_r) & ((dx * hx + dy * hy) * invd >= kin_cos)
        kin_vis[ar, idx] = False
        dead_cols = None if self.alive is None else ~self.alive
        if dead_cols is not None:
            # 통합 무대 (k): 시체는 동족이 아니다(동족 수·무리 중심·분리·kin_alarm). 스텝 끝 관측에서는 이번 스텝에 죽은 개체가 아직 산 슬롯이라
            # 죽은 자리에서 동족으로 세어진다(C++ 관측 E 가 리스폰·목록 빼기 앞이다)
            kin_vis[:, dead_cols] = False
        kin_f = kin_vis.astype(np.float64)
        kin_count = kin_f.sum(1)
        centroid = (kin_f @ self.pos) / np.maximum(kin_count, 1.0)[:, None]
        to_centroid = np.where(kin_count[:, None] > 0, normalize(centroid - P), 0.0)

        # --- separation: 반경 내 이웃마다 (1 - d/R) * 멀어지는 단위벡터, 합 후 크기 1로 clamp ---
        # sum_j w_ij * (pos_j - P_i)/d_ij  =  (c @ pos) - rowsum(c) * P,  c = w/d
        wgt = np.clip(1.0 - dist / cfg.sep_radius, 0.0, None)
        wgt[ar, idx] = 0.0
        if dead_cols is not None:
            wgt[:, dead_cols] = 0.0
        c = wgt * invd
        separation = clamp_magnitude(-((c @ self.pos) - c.sum(1)[:, None] * P), 1.0)

        # --- 포식자 (§3.1 idx1, idx2) ---
        rz: dict = {}
        if self.M > 0:
            ex = self.pred_pos[:, 0][None, :] - P[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - P[:, 1:2]
            pd = np.sqrt(ex * ex + ey * ey)
            pinv = 1.0 / np.maximum(pd, EPS)
            # v2.4: 초식의 포식자 탐지 반경만 see_r·(1 − detect_night·d) 로 준다(계획서 4.9.2 (a)). 동족 시야(위)·관측 2 의
            # 분모·조향 도주 문턱(steering.py)은 see_r 그대로다. d = 0 이면 see_r·1.0 이라 v2.1 과 비트 단위로 같다
            see_p = cfg.see_r if self._dn is None else self._see_pred
            if self._rp is not None:    # v3: 개체 행동별 자기 탐지 반경(GRAZE 고개 숙임 M5, SLEEP 시야)
                see_p = see_p * self._rep_see[idx][:, None]
            if self._zv is None:
                pvis = (pd <= see_p) & ((ex * hx + ey * hy) * pinv >= fov_cos)
            else:                       # v3 현실성 (a): 위협 시야각 threat_fov_deg (반경은 그대로)
                pcos = (ex * hx + ey * hy) * pinv
                pvis = (pd <= see_p) & (pcos >= self._zv["threat_cos"])
                rear = pvis & ~(pcos >= fov_cos)        # 통계 전용: 기본 시야각 밖에서 본 위협
            if self._ob is not None and self._ob["block_sight"] and len(self.obstacles):
                # 야생 2단계 3 의 3): 원판이 눈길을 가린다(발소리는 아래에서 그대로 더한다)
                pvis, n_pair, n_blk = self._ob_occlude(pvis, P, self.pred_pos)
                if len(idx) == self.N:          # 통계 전용: 스텝 관측(전체 행)만 센다
                    self._ob_eye_pairs += n_pair
                    self._ob_eye_blocked += n_blk
            if self._zh is not None:
                # v3 현실성 (b): 지난 스텝에 움직인 위협의 발소리 — 실거리 ≤ min(R, 이 사슴의 지금 탐지 반경)이면 방향과 무관하게
                # 감지된다(보임과 같은 칸). R = 0 인 위협(서 있음·대치·휴식)은 들리지 않는다. 걸음새는 지난 포식자 스텝의 훅
                zh = self._zh
                r_snd = hearing_radius(zh, np.sqrt((self.pred_vel * self.pred_vel).sum(1)) / cfg.herb_speed,
                                       self.pred_running)[None, :]
                lim = np.minimum(r_snd, see_p) if zh["cap_to_sight"] else r_snd
                sight = pvis
                pvis = pvis | ((pd <= lim) & (r_snd > 0.0))
            if self._ps is not None:    # v2.4s: 자는 포식자는 굴에 있어 보이지 않는다(관측 1·2·도주 조향에서 빠진다)
                pvis &= ~self.pred_asleep[None, :]
            if self._zv is not None or self._zh is not None:
                # 통계 전용(realism_stats, 관측·동역학에 들어가지 않는다): 눈으로 본 위협(eye)이 넓힌 시야각에만 있었나, 들어서만 알았나
                eye = pvis if self._zh is None else (
                    sight & ~self.pred_asleep[None, :] if self._ps is not None else sight)
                if self._zv is not None:
                    rz["rz_rear"] = eye.any(1) & ~(eye & ~rear).any(1)
                if self._zh is not None:
                    rz["rz_heard"] = pvis.any(1) & ~eye.any(1)
            if self._wf is not None or self.keep_pair_vis:
                rz["wf_pvis"] = pvis.copy()     # 야생 (w3) 알아챔(사슴 × 위협, 관측과 같은 보임) — 진단 실행기도 읽는다
            pred_count = pvis.sum(1)
            masked = np.where(pvis, pd, np.inf)
            j = masked.argmin(1)
            d_pred_min = masked[ar, j]
            seen = np.isfinite(d_pred_min)[:, None]
            away = np.where(
                seen, -np.stack([ex[ar, j], ey[ar, j]], 1) * pinv[ar, j][:, None], 0.0
            )
        else:
            pred_count = np.zeros(n, dtype=np.int64)
            d_pred_min = np.full(n, np.inf)
            away = np.zeros((n, 2))
            if self._zv is not None:
                rz["rz_rear"] = np.zeros(n, dtype=bool)
            if self._zh is not None:
                rz["rz_heard"] = np.zeros(n, dtype=bool)
            if self._wf is not None or self.keep_pair_vis:
                rz["wf_pvis"] = np.zeros((n, 0), dtype=bool)

        # --- 은신처 (§3.1 idx6) ---
        if len(self.cov_r):
            cx, cy, edge = self._cover_edge(P)
            k = edge.argmin(1)
            e = edge[ar, k]
            in_cover = e <= 0.0
            cover_dist = np.clip(np.maximum(e, 0.0) / cfg.obs_cover_norm, 0.0, 1.0)
            to_cover = np.where(
                in_cover[:, None], 0.0, normalize(np.stack([cx[ar, k], cy[ar, k]], 1))
            )
        else:
            in_cover = np.zeros(n, dtype=bool)
            cover_dist = np.ones(n)
            to_cover = np.zeros((n, 2))

        # --- 먹이 (§3.1 idx0) ---
        ix, iy = self._cell_index(P)
        food_density = self.food_blur[iy, ix]
        food_grad = normalize(np.stack([self._food_gx[iy, ix], self._food_gy[iy, ix]], 1))

        vals = dict(
            food_grad=food_grad,
            food_density=food_density,
            to_centroid=to_centroid,
            kin_count=kin_count,
            separation=separation,
            d_pred_min=d_pred_min,
            pred_count=pred_count,
            away_from_pred=away,
            to_cover=to_cover,
            cover_dist=cover_dist,
            in_cover=in_cover,
        )
        if self._rp is not None:
            # v3 (repertoire 관측·사건 입력): 가장 가까운 보이는 위협의 접근 속력 c = clip(v_pred·û / herb_speed, −1, 1)
            # (û = 위협에서 이 개체 쪽 단위벡터, v_pred = 그 위협의 지난 스텝 이동)를 (c + 1)/2 로, 없으면 0.5.
            # kin_alarm = 보이는 동족 중 FLEE 비율(없으면 0). cover_k = 가장 가까운 은신처 색인(가장자리 거리, 동점이면 낮은
            # 색인, 은신처가 없으면 −1).
            # *_ev = 사건 비교 시야(이번 관측과 직전 관측의 행동 시야 배수 중 작은 쪽)로 센 포식자 수·가장 가까운 거리·접근 속력.
            # 사건 E1·E2 만 쓴다 — 자기 행동이 바뀌어 시야가 넓어진 것만으로 생긴 위협은 사건이 아니다(repertoire docstring A.b)
            if self.M > 0:
                pv = self.pred_vel[j]
                c = -(pv[:, 0] * ex[ar, j] + pv[:, 1] * ey[ar, j]) * pinv[ar, j] / cfg.herb_speed
                vals["pred_approach"] = np.where(seen[:, 0], (np.clip(c, -1.0, 1.0) + 1.0) * 0.5, 0.5)
                lo = np.minimum(self._rep_see[idx], self._rep_see_last[idx])
                base_r = cfg.see_r if self._dn is None else self._see_pred
                pvis_e = pvis & (pd <= base_r * lo[:, None])
                masked_e = np.where(pvis_e, pd, np.inf)
                je = masked_e.argmin(1)
                seen_e = np.isfinite(masked_e[ar, je])
                pve = self.pred_vel[je]
                ce = -(pve[:, 0] * ex[ar, je] + pve[:, 1] * ey[ar, je]) * pinv[ar, je] / cfg.herb_speed
                vals["pred_count_ev"] = pvis_e.sum(1)
                vals["d_pred_min_ev"] = masked_e[ar, je]
                vals["pred_approach_ev"] = np.where(seen_e, (np.clip(ce, -1.0, 1.0) + 1.0) * 0.5, 0.5)
            else:
                vals["pred_approach"] = np.full(n, 0.5)
                vals["pred_count_ev"] = np.zeros(n, dtype=np.int64)
                vals["d_pred_min_ev"] = np.full(n, np.inf)
                vals["pred_approach_ev"] = np.full(n, 0.5)
            flee = (self._rs.behavior == rep.FLEE).astype(np.float64)
            vals["kin_alarm"] = np.where(kin_count > 0, (kin_f @ flee) / np.maximum(kin_count, 1.0), 0.0)
            vals["cover_k"] = k if len(self.cov_r) else np.full(n, -1, dtype=np.int64)
            if self._al is not None:    # v3 R2 M8 통계 전용(헛경보): 가장 가까운 보이는 위협의 색인, 없으면 −1
                vals["pred_j"] = (np.where(seen[:, 0], j, -1).astype(np.int64) if self.M > 0
                                  else np.full(n, -1, dtype=np.int64))
        vals.update(rz)                 # v3 현실성 통계 전용 칸(켠 규칙만)
        if out is None:
            return vals
        for key, v in vals.items():
            out[key][idx] = v
        return out

    # ------------------------------------------------------------------ #
    # 관측 (§3.1)
    # ------------------------------------------------------------------ #

    def _obs_from(self, g: dict, idx: np.ndarray | None = None) -> np.ndarray:
        """§3.1 — v1 7개(+ 켠 기능의 칸, `obs_names`), float32, [0,1]. 정규화 상수는 전부 고정값이다 (§1.2).

        v2.2 idx 7 threat_recency 는 `_perceive` 가 이 관측의 기하로 갱신한 값 그대로다(이미 [0,1]).
        """
        cfg = self.cfg
        sl = slice(None) if idx is None else idx
        n = self.N if idx is None else len(idx)
        o = np.empty((n, self.obs_dim), dtype=np.float32)
        o[:, OBS_FOOD_DENSITY] = np.clip(g["food_density"][sl], 0.0, 1.0)
        o[:, OBS_PREDATOR_COUNT] = np.clip(g["pred_count"][sl] / cfg.obs_pred_count_norm, 0.0, 1.0)
        o[:, OBS_PREDATOR_DISTANCE] = np.clip(g["d_pred_min"][sl] / cfg.see_r, 0.0, 1.0)
        o[:, OBS_KIN_COUNT] = np.clip(g["kin_count"][sl] / cfg.obs_kin_count_norm, 0.0, 1.0)
        o[:, OBS_ENERGY] = np.clip(self.energy[sl] / cfg.max_energy, 0.0, 1.0)
        o[:, OBS_RECENT_PREDATION] = min(self.pred_ema, 1.0)
        o[:, OBS_COVER_DISTANCE] = g["cover_dist"][sl]
        if self._vg is not None:
            o[:, OBS_THREAT_RECENCY] = self.threat[sl]
        if self._dn is not None:        # v2.4 전역 값 두 칸 (계획서 4.2 visibility·to_transition, 이미 [0,1])
            o[:, self._obs_vis] = self._vis
            o[:, self._obs_tt] = self._to_tr
        if self._obs_rep is not None:   # v3 추가 관측 9칸 (obs_extra true 일 때만)
            o[:, self._obs_rep:self._obs_rep + len(rep.OBS_EXTRA_NAMES)] = rep.obs_extra(self._rs, self._rp, g, idx)
        if self._obs_alarm is not None:  # v3 R2 M8 alarm_heard (E′ 뒤 경보 상태, 리스폰 개체는 0)
            o[:, self._obs_alarm] = rep.alarm_level(self._rs, self._al, idx)
        return o

    def _observe_subset(self, idx: np.ndarray) -> np.ndarray:
        """§4.5 — 리스폰된 슬롯만 재계산한다. v2.2 는 리스폰이 0 으로 되돌린 threat_recency 를 이 관측으로 갱신한다."""
        self._geometry(idx, out=self._g)
        if self._vg is not None:
            self._perceive(self._g, idx)
        if self._rp is not None:
            rep.perceive(self._rs, self._rp, self._g, idx)
        return self._obs_from(self._g, idx)

    def _perceive(self, g: dict, idx: np.ndarray | None = None) -> None:
        """v2.2 threat_recency·ThreatDir 갱신 (계획서 4.2 idx 7, 4.4). 관측을 만들 때마다 개체당 한 번 부른다.

        '보임' = 이 관측의 포식자 수(관측 1)가 0 보다 크다 — 기본 FOV 120°, 직전 스텝에 경계한 개체는 경계 시야
        (`_geometry`). 반경은 see_r 그대로다.
          r ← 1                  (보임)
          r ← decay · r          (안 보임)
          ThreatDir ← 가장 가까운 보이는 포식자 쪽 단위벡터 (= −away_from_pred. 보일 때만 바꾸고 안 보이면 그대로)
        부르는 때: reset(r = 0·ThreatDir = 0 에서 첫 관측으로), 스텝 끝 8) 관측(스텝마다 한 번 → 놓친 뒤 k 스텝이면
        r = decay^k), 리스폰(`_respawn` 이 r = 0·ThreatDir = 0 으로 되돌린 뒤 리스폰 관측으로. 리스폰 자리에서 포식자가
        보이면 1, 아니면 0). 죽은 개체의 terminal_obs 는 리스폰 전 값(죽은 스텝 끝 관측)이다.
        C++ 꼴: Recency = (PredCount > 0) ? 1 : Decay * Recency; if (PredCount > 0) ThreatDir = ToNearestPred.

        같은 때에 통계 전용 기준 상태도 갱신한다(관측·동역학에 들어가지 않는다, C++ 로 옮기지 않는다):
        `_near` = 이 관측 위치에서 거리 ≤ see_r 인 포식자가 있다(FOV 무시, `_geometry` 와 같은 거리 식이라
        보임 ⇒ 반경 안), `_tr_truth` = 같은 규칙의 흔적(반경 안이면 1, 아니면 × decay, 리스폰 0).
        """
        sl = slice(None) if idx is None else idx
        decay = self._vg["decay"]
        seen = g["pred_count"][sl] > 0
        r = self.threat[sl] * decay
        r[seen] = 1.0
        self.threat[sl] = r
        td = self.threat_dir[sl]
        td[seen] = -g["away_from_pred"][sl][seen]
        self.threat_dir[sl] = td
        P = self.pos[sl]
        if self.M > 0:
            ex = self.pred_pos[:, 0][None, :] - P[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - P[:, 1:2]
            near = (np.sqrt(ex * ex + ey * ey) <= self.cfg.see_r).any(1)
        else:
            near = np.zeros(len(P), dtype=bool)
        tr = self._tr_truth[sl] * decay
        tr[near] = 1.0
        self._tr_truth[sl] = tr
        self._near[sl] = near

    def observe(self) -> np.ndarray:
        return self._obs

    # ------------------------------------------------------------------ #
    # step (§4.5)
    # ------------------------------------------------------------------ #

    def _check_action(self, a: np.ndarray) -> None:
        """행동 배열 모양 (N, act_dim). 행동 4개(v1)를 speed·vigilance 를 켠 세계에 넣으면 그 열이 없어 여기서 멈춘다."""
        if a.ndim != 2 or a.shape != (self.N, self.act_dim):
            raise ValueError(
                f"행동은 ({self.N}, {self.act_dim}) [{', '.join(self.act_names)}] 이어야 한다. 받은 모양: {a.shape}"
                + (". v1 정책(Utility·random 4개)은 speed 를 켠 세계에 그대로 쓸 수 없다" if self.act_dim != ACT_DIM
                   and a.ndim == 2 and a.shape[1] == ACT_DIM else ""))

    def step(self, a: np.ndarray):
        """`a`: (N, act_dim) in [0,1] (§1.3). act_dim 은 v1 4, speed 를 켜면 5, vigilance 까지 켜면 6.
        repertoire(v3)를 켜면 act_dim 1 이고 값은 정수 행동 번호(0..4)다(정수가 아니면 ValueError).
        반환: obs, reward, done, terminal_obs.

        speed(v2.1)를 켠 세계의 스텝 순서는 `_gait_step`, vigilance(v2.2)는 `_vigil_step`, repertoire(v3)는
        env_v2/repertoire.py 모듈 docstring 과 `_rep_step` 에 적었다. 끈 세계는 v1 과 같은 줄을 탄다.
        """
        cfg = self.cfg
        a = np.asarray(a, dtype=np.float64)
        self._check_action(a)
        rew = np.full(self.N, cfg.rew_alive)
        vg, vw, rp = self._vg, self._vw, self._rp
        # 통합 무대 (k) 부활 없음: 이번 스텝 첫머리의 산 슬롯 L. self.alive 는 스텝 끝(관측 뒤)에 새 배열로 바뀐다 — 그때까지 L 과 같다.
        # 부활 있는 세계는 None 이고 아래 L 분기를 타지 않는다
        live = self.alive
        if vg is not None:
            ema0 = min(self.pred_ema, 1.0)              # 결정 때 관측 5 (vigil_stats B5′ 용, 6) 에서 바뀐다)
        if vw is not None:              # v2.2r 0) 결정 때 창: 결정 관측의 포식자 수 0 & threat_recency > theta
            self.window = (self._g["pred_count"] == 0) & (self.threat > vw["theta"])

        if rp is not None:
            # v3 0r·1r) 행동 실행기: 결정 시점에만 요청을 받고(잠금·사건·지연), 행동별 제어기가 속도·보행을 정한다
            v, rep_out = self._rep_step(a)
            if self._al is not None and self._al["active"]:
                self._alarm_emit_step(rep_out)          # v3 R2 A′: 경보 방출 목록, alarm_new ← False
        else:
            # 1) 초식 이동 — §3.3 조향 수식. 벽 경계(§4.2), 토러스 없음.
            #    v2.2 threat_flee > 0 (#18 변형, Gate E2b 보고 팔)만 위협 반대 항을 정규화 전에 더한다. 0 이면 None 이라
            #    steer 가 v1 줄 그대로다.
            v = steer(self._g, a, cfg,
                      self._threat_flee_term() if vg is not None and vg["threat_flee"] > 0.0 else None)
            if self._sp is not None:
                v = self._gait_step(v, a[:, ACT_SPEED])     # v2.1: 보행 상태가 크기만 바꾼다. 방향은 v1 조향 그대로
            if self._act_vig is not None:       # v2.2: 경계면 속력 0 (speed 보다 우선). v2.2r W′ 는 창 안에서만
                v = self._vigil_step(v, a[:, self._act_vig],
                                     self.window if vw is not None and vw["window_only"] else None)
        if self._wr is not None:
            # 야생 (w1) 약함: 스텝 첫머리 E 가 weak_e 밑이면(비축으로 사는 몸) 이동 속도 × weak_speed. 대사·섭식은 보행 그대로. 적용 속도 훅도 줄인 값
            self.weak = self.energy < self._wr["weak_e"] * cfg.max_energy
            if self._wr["weak_speed"] < 1.0 and self.weak.any():
                v = np.where(self.weak[:, None], v * self._wr["weak_speed"], v)
                self.vel = v
        if live is not None:
            # 통합 무대 (k): 시체는 움직이지 않는다(죽은 자리에 멈춘다 — C++ 처리기가 목록에서 뺀다). 적용 속도 훅도 0 이다
            v = np.where(live[:, None], v, 0.0)
            self.vel = v
        if self._zt is not None:
            # v3 R3 (h): 이동 전 위치 셀의 땅이 속도를 줄인다(모든 행동). 대사·섭식은 보행 상태 그대로다. 적용 속도 훅 vel 도 줄인 값이다
            tc = self._rz_terrain_of(self.pos)
            v = v * self._zt["mult_herb"][tc][:, None]
            self.vel = v
            self._zt_deer += np.bincount(tc, minlength=len(TERRAIN_NAMES))
        if self._wp is not None:
            self._pack_p0 = self.pos.copy()     # 야생 2단계 2: 사슴의 이번 스텝 이동(도주 방향)을 포식자 스텝이 읽는다
        p_before = self.pos
        self.pos = np.clip(self.pos + v, 0.0, self.size)
        if self._ob is not None and len(self.obstacles):
            # 야생 2단계 3 의 2): 원판 앞에서 멈춰 둘레를 따라 미끄러진다(되풀이마다 무대로 자르고, 끝에 원판 안이면 마지막으로 닿은 자리로 물러남).
            # heading·적용 속도 훅은 가려던 방향 그대로다
            self.pos, hit, back = obstacle_slide(p_before, self.pos, self.obstacles, self._ob["body_r"], self.size)
            self._ob_deer_hit += int(np.count_nonzero(hit))
            self._ob_deer_back += int(np.count_nonzero(back))
            self._ob_deer_steps += self.N if live is None else int(np.count_nonzero(live))
        moving = np.linalg.norm(v, axis=1) > EPS
        self.head = np.where(moving[:, None], normalize(v), self.head)
        if rp is not None:                  # v3: FREEZE 는 위협 쪽을 본다(모르면 그대로)
            face = (rep_out["face"] != 0.0).any(1)
            if live is not None:
                face &= live                # 통합 무대 (k): 시체는 돌아보지 않는다
            self.head[face] = rep_out["face"][face]
        if vg is not None:                  # v2.2 1e): 경계한 개체는 위협 쪽을 본다(ThreatDir, 본 적 없으면 유지)
            self._face_threat()
        if vw is not None and vw["look_back"]:   # v2.2r 1f): 정지 중이고 창 안이면 위협 쪽을 본다(L 반사)
            self._look_back()

        # 2) 포식자 이동 + 포획 판정 (v3 는 정지 탐지·상태별 은신 배수·잠행형·플레이어)
        caught = self._step_predators_v3() if self._v3p else self._step_predators()
        if self._zt is not None and caught.any():      # v3 R3 (h) 통계 전용: 잡힌 순간(초식 이동 뒤) 사슴 위치의 땅
            self._zt_catch += np.bincount(self._rz_terrain_of(self.pos[caught]), minlength=len(TERRAIN_NAMES))
        if self._al is not None and self._al["active"] and self._al["on_catch"] and caught.any():
            self._alarm_cry(caught)                     # v3 R2 M8: 잡힌 개체의 비명(홉 0, 점 = 잡은 위협 위치)
        if self._wr is not None and caught.any():       # 야생 (w1) 통계 전용: 약한 채로 잡힌 수
            self._wr_weak_caught += int(np.count_nonzero(caught & self.weak))

        # 3) 섭식 · 대사 (§3.4 "에너지 획득 +1.0 × 획득량")
        if self._sp is None and vg is None and self._dn is None:
            e_drained = self.energy - cfg.energy_drain
            gain = self._eat(e_drained)
        else:                       # v2.1·v2.2·v2.4: 대사와 섭식 배수가 이번 스텝의 실제 보행·경계·어둠을 따른다
            drain, eat = self._drain_eat()
            if live is not None:
                # 통합 무대 (k): 시체는 먹이를 찾지 않는다 — 셀 수요 합에 0 을 더하므로 산 개체의 몫이 시체가 없는 세계와 같다
                eat = eat * live
            e_drained = self.energy - drain
            gain = self._eat(e_drained, eat)
        if self._zf is not None:    # v3 현실성 (e) 통계 전용: 은신처 원 안(섭식 위치)에서 먹은 몫
            inc = self._in_cover(self.pos)
            self._zf_in += float(gain[inc].sum())
            self._zf_all += float(gain.sum())
        e_new = np.minimum(e_drained + gain * cfg.food_energy_per_unit, cfg.max_energy)
        if live is not None:
            e_new = np.where(live, e_new, self.energy)     # 통합 무대 (k): 시체의 에너지는 죽은 때 값에 멈춘다(대사도 없다)
        if self._wr is not None:
            e_new = self._wild_reserve_step(e_new, gain * cfg.food_energy_per_unit, live)   # 야생 (w1): 모자람은 비축에서, 남음은 비축으로
        if self._sp is not None and self._sp["net_energy_reward"]:
            # #4 순변화 e_new − e_prev. 번식 리셋(아래 4)과 리스폰(8)은 이 뒤라 들어가지 않는다
            rew += cfg.rew_energy * (e_new - self.energy)
        else:
            rew += cfg.rew_energy * (e_new - e_drained)
        e_prev = self.energy
        self.energy = e_new

        # 4) 번식 — energy > threshold AND repro_cd == 0 (§3.4)
        self.repro_cd = np.maximum(self.repro_cd - 1, 0)
        repro = (self.energy > cfg.repro_threshold) & (self.repro_cd == 0)
        if live is not None:
            # 통합 무대 (k): 시체는 번식하지 않는다. 이번 스텝에 잡힌 개체는 아직 L 이라 번식할 수 있다(C++ C5 가 C6 사망 판정 앞이다).
            # 번식으로 태어나는 다음 단계(아직 없음)는 여기서 repro 개체마다 빈 슬롯(~self.alive)에 `_spawn_slots` 를 부른다 — `_ist_bury`
            repro &= live
        if repro.any():
            rew += cfg.rew_repro * repro
            self.energy = np.where(repro, cfg.init_energy, self.energy)
            self.repro_cd = np.where(repro, int(cfg.repro_cd), self.repro_cd)

        # 5) 사망: 피식 또는 아사
        starved = self.energy <= 0.0
        if self._wr is not None:
            starved &= self.reserve <= 0.0              # 야생 (w1): 비축까지 바닥나야 굶어 죽는다
        if live is not None:
            # 통합 무대 (k): 굶음 = 산 개체 중 잡히지 않은 E ≤ 0 (C++ Stats.Starved 의 정의. 잡힌 개체는 포획으로만 센다)
            starved &= live & ~caught
        done = caught | starved
        rew += cfg.rew_death * done
        if live is not None:
            rew = np.where(live, rew, 0.0)              # 통합 무대 (k): 시체의 행은 보상이 없다(학습에 쓸 때는 손실에서 뺀다)

        # 6) 지역 피식 EMA (§3.1). §9.6과 맞춰 피식 사망만 센다.
        #    통합 무대 (l) 는 분모를 ema_den 으로 둔다(null 이면 N — 지금 그대로)
        n_pred_deaths = int(caught.sum())
        ema_den = self.N if self._ist is None or self._ist["ema_den"] is None else self._ist["ema_den"]
        self.pred_ema = (
            cfg.predation_ema_decay * self.pred_ema
            + (1.0 - cfg.predation_ema_decay) * (n_pred_deaths / ema_den) * cfg.predation_ema_gain
        )

        # 7) 먹이 재생 (§4.2). 셀 용량(패치 구조)을 향해 자란다.
        #    은신처 셀은 이미 0.3배가 반영된 regen_field.
        if self._fv is None:
            self.food += self.regen_field * (self.food_cap - self.food)
            np.clip(self.food, 0.0, self.food_cap, out=self.food)
        else:
            self._food_v_step()        # v2.0b: 훼손 → 재생(목표·상한 V) → 휴식 회복

        self.t += 1
        self._accumulate(a if rp is None else self._rep_a4, rew, repro, caught, starved, done)
        if rp is not None:            # v3: 결정 때 상태(어둠·위협 보임)와 이번 스텝 행동으로 레퍼토리 지표를 센 뒤 시간을 넘긴다
            self._rep_accumulate(rep_out, caught, starved)
            self._rep_export()
            rep.tick(self._rs)
        if self._sp is not None:      # 스텝 전 기하(self._g)·결정 때 에너지로 보행 지표를 센다
            self._gait_accumulate(e_prev, e_new - e_drained, drain)
        if vw is not None:            # 결정 때 창·배부름으로 창 지표(B3_L·W′ 사용률)를 센다
            self._window_accumulate(e_prev)
        if vg is not None:            # 결정 때 상태(기하·threat_recency·시야·에너지)로 경계 지표를 센다
            flee = self._vigil_accumulate(a, e_prev, ema0, moving)
            self._wide = self.vigilant.copy()       # 8a) 이번 스텝에 경계한 개체의 다음 관측은 경계 시야다
        if self._dn is not None:
            # v2.4: 결정 때 어둠(이번 스텝 동역학의 d)으로 위상 지표를 센 뒤, 새 t 의 어둠·탐지 반경·관측 값을 정한다.
            # 아래 8) 의 기하·관측과 다음 스텝의 섭식·휴식 대사가 이 값을 쓴다
            self._daynight_accumulate(e_prev, caught, starved, e_new - e_drained, drain)
            self._daynight_update()

        # 8) 관측 — 스텝당 observe() 한 번 (§4.5)
        g = self._geometry()
        if self._zv is not None or self._zh is not None:   # v3 현실성 통계 전용: 스텝 끝 관측(리스폰 전)의 넓힌 시야·청각 몫
            self._rz_obs_n += self.N
            if self._zv is not None:
                self._rz_rear_n += int(np.count_nonzero(g["rz_rear"]))
            if self._zh is not None:
                self._rz_heard_n += int(np.count_nonzero(g["rz_heard"]))
        if vg is not None:
            self._perceive(g)                       # 8b) threat_recency·ThreatDir
            if vg["fov_deg"] >= 360.0:              # 8c) 360° 경계 시야로 새로 찾은 포식자 쪽을 본다 (4.4 경계 행)
                self._face_threat()
            self._b4_accumulate(flee, g, done)
        if rp is not None:
            rep.perceive(self._rs, rp, g)           # v3: 마지막 위협 방향·threat_recency
            if self._al is not None and self._al["active"]:
                self._alarm_receive_step(g)         # v3 R2 E′: 경보 받기(관측 전, 리스폰 전)
        obs = self._obs_from(g)
        self._g, self._obs = g, obs
        terminal_obs = obs.copy()
        if done.any():
            dead = np.flatnonzero(done)
            if live is not None:
                self._ist_bury(dead, caught)      # 통합 무대 (k): 되살리지 않는다(시체로 남긴다, 리스폰 난수·관측 없음)
            else:
                self._respawn(dead)
                obs[dead] = self._observe_subset(dead)
                if self._sp is not None:
                    self._gait_prev[:, dead] = -1     # 새 개체: 보행 전환(B8)을 이전 개체와 잇지 않는다
                if vg is not None:
                    self._vig_prev[dead] = -1         # 새 개체: 경계 전환(b8_vig)도 잇지 않는다
        if self._wf is not None:
            self._wf_update(done)               # 야생 (w3): 스텝 끝 기하(리스폰 관측 포함)로 다음 스텝의 덮기를 정한다

        return obs, rew, done, terminal_obs

    def _drain_eat(self) -> tuple[np.ndarray, np.ndarray]:
        """`step` 3) 의 개체별 (대사, 섭식 배수). speed·vigilance 중 하나라도 켠 세계에서만 부른다.

        - speed: 대사 energy_drain × drain_mult[실제 보행], 섭식 gait_eat[실제 보행] (v2.1 그대로)
        - speed 를 끈 세계: 대사 energy_drain(v1), 섭식 1 (v1 그대로. 보행이 없어 대사가 속력과 무관하다)
        - vigilance: 경계한 개체의 섭식 배수만 eat_mult 로 바꾼다. 대사는 바꾸지 않는다 — 경계 개체의 실제 보행은
          정지(`_vigil_step`)라 speed 세계에서는 정지 대사 c_rest(= drain_mult[정지]), speed 를 끈 세계에서는 v1 대사다
        """
        cfg = self.cfg
        if self._rp is not None:
            # v3 (명세 2절 표): 대사·섭식 배수는 행동 제어기(`repertoire.control`)가 정한다 — 대사 = 보행 대사, SLEEP 이고
            # 은신처 안이면 × (1 − sleep_rest·d)(휴식 할인은 SLEEP 전용이라 daynight.rest_night 는 쓰지 않는다), 섭식 =
            # GRAZE 정지 1·걷기 0.5, 그 밖 0. 섭식에는 밤 배수 (1 − eat_night·d) 를 곱한다.
            # C++ 꼴: Drain = EnergyDrain * DrainMult(B, G, bInCover, D); Want *= EatMult(B, G) * (1 − EatNight·D)
            return cfg.energy_drain * self._rep_drain, self._rep_eat * (1.0 - self._dn["eat_night"] * self.dark)
        if self._sp is not None:
            drain = cfg.energy_drain * self._sp["drain_mult"][self.gait]
            eat = self._sp["eat"][self.gait]
        else:
            drain = np.full(self.N, cfg.energy_drain)
            eat = np.ones(self.N)
        if self._vg is not None:
            eat = np.where(self.vigilant, self._vg["eat_mult"], eat)
        if self._dn is not None:
            # v2.4 (계획서 4.9.2 (b)(c)): 결정 때 어둠 d 로 섭식 × (1 − eat_night·d), 정지·비경계 개체의 대사 ×
            # (1 − rest_night·d). 정지에는 방향이 없어 멈춘 개체(stall)도 든다. d = 0 이면 × 1.0 이라 v2.1 과 같다.
            # C++ 꼴: Want *= GaitEat[G] * (1 − EatNight·D); Drain = EnergyDrain * DrainMult[G] * (bRest ? 1 − RestNight·D : 1)
            dn, d = self._dn, self.dark
            eat = eat * (1.0 - dn["eat_night"] * d)
            rest = self.gait == GAIT_STOP
            if self._vg is not None:
                rest = rest & ~self.vigilant
            if dn["rest_cover_only"]:       # v2.4b: 은신처 안에서 멈춘 개체만(정지 개체는 움직이지 않아 결정 때 위치 그대로)
                rest = rest & self._g["in_cover"]
            drain = np.where(rest, drain * (1.0 - dn["rest_night"] * d), drain)
        return drain, eat

    def _vigil_step(self, v: np.ndarray, a_vig: np.ndarray, win: np.ndarray | None = None) -> np.ndarray:
        """v2.2 경계 (계획서 4.3·4.4 1단계 표, #1·#5). `step` 1) 에서 보행(`_gait_step`) 뒤에 부른다.

        v2.2r W′(vigil_window.window_only)면 `win`(결정 때 창, `step` 0)을 받아 1a') 를 vig = a_vig > threshold & win
        으로 바꾼다 — 창 밖에서는 경계가 효력이 없고 speed 가 보행을 정한다. 나머지 순서는 아래 그대로다.
        C++ 꼴: bVig = A[Vig] > Threshold && (!bWindowOnly || bWindow).

        한 스텝 순서 — C++ 로 옮길 때 이 순서를 지킨다. 행동 쪽은 상태가 없다(문턱 고정, 최소 유지 시간 없음):
          1-)  (step, threat_flee > 0 일 때만) v1 조향 합에 #18 위협 반대 항을 더한 뒤 정규화한다(`_threat_flee_term`).
               threat_flee = 0(configs/v2_2.yaml)이면 이 단계가 없다
          1a') 경계 vig = a_vig > threshold (sigmoid 뒤 [0,1] 값. 같으면 경계가 아니다)
          1b') 경계면 v ← 0 — speed 명령보다 우선한다. speed 세계에서는 실제 보행 gait ← 정지(gait_cmd 는 speed 명령
               그대로). 그래서 대사는 정지 대사, 섭식은 eat_mult(`_drain_eat`)다
          1d)  (step) pos ← clip(pos + v), |v| > EPS 면 heading ← v 방향 — v1 줄 그대로. 경계는 v = 0 이라 여기서는 유지
          1e)  (step) 경계면 heading ← ThreatDir (단위벡터, 0 이면 유지, `_face_threat`). ThreatDir 는 결정 때 관측
               (이전 스텝 끝 8b)에서 갱신했으므로 '결정 때 포식자가 보였으면 가장 가까운 포식자 쪽, 아니면 마지막 위협
               방향'이다
          2)~7) (step) 포식자·섭식·대사·번식·사망·재생. 포식자는 경계를 모른다(v1 그대로)
          8a)  (step) 다음 관측의 시야 ← vig. 경계한 개체는 시야각 fov_deg(360°)·반경 see_r 로 동족·포식자를 본다
               (관측 1·2·3·조향 기하). 리스폰 개체는 기본 시야로 되돌린다(`_respawn`)
          8b)  (step) threat_recency·ThreatDir 갱신 (`_perceive`)
          8c)  (step, fov_deg = 360 일 때만) 경계면 heading ← ThreatDir 를 한 번 더 한다(`_face_threat`, 리스폰 전).
               8b 가 360° 경계 시야로 새로 찾은 포식자(경계를 시작한 스텝의 결정 관측 120° 로는 안 보이던 뒤쪽 포식자
               포함) 쪽을 스텝 끝 heading 으로 남긴다 — 4.4 경계 행 '보이면 가장 가까운 포식자 쪽'. 360° 시야의
               기하는 heading 을 쓰지 않으므로(각도 판정 −inf) 이미 만든 관측이 그대로 맞다. fov_deg < 360 이면 하지
               않는다(heading 을 바꾸면 그 heading 으로 잰 관측과 어긋난다). 그때 스텝 끝 heading 은 1e 의 값이고,
               그 스텝에 처음 본 포식자 쪽은 다음 경계 스텝의 1e 에서 돈다
        경계 중 FOV 가 360° 라 바라보는 방향은 그 스텝의 탐지에 영향이 없다(4.4 '위협 쪽 보기는 연출'). 다만 경계를
        풀고 멈춰 서면 heading 이 유지되므로 그때의 120° 시야는 마지막 경계 스텝 끝에 본 위협 쪽을 향한다(8c. 한 스텝짜리
        경계도 그 스텝에 360° 로 찾은 포식자 쪽을 남긴다). fov_deg = 360 에서 스텝 끝 heading 은 8c 만으로 정해지고
        1e 는 2)~8b 사이의 중간 값만 바꾼다(그 사이에 heading 을 읽는 단계가 없다).
        C++ 꼴: bVig = A[Vig] > Threshold; if (bVig) { Velocity = 0; Gait = Stop; if (!ThreatDir.IsZero())
                Facing = ThreatDir; } Want *= bVig ? EatMult : GaitEat[Gait]; 다음 Perception 의 FOV = bVig ? 360 : 120.
                Perception(ThreatDir 갱신) 뒤: if (bVig && Fov >= 360 && !ThreatDir.IsZero()) Facing = ThreatDir;
        스텝 뒤 훅(replay_v2): `self.vigilant`, `self.gaze`(스텝 뒤 heading, 리스폰 전), `self.vel`(적용 속도).
        리스폰은 이 훅을 바꾸지 않는다(죽은 슬롯의 마지막 프레임이 그 개체의 값이다).
        """
        vig = a_vig > self._vg["threshold"]
        if win is not None:
            vig = vig & win
        v = np.where(vig[:, None], 0.0, v)
        if self._sp is not None:
            self.gait = np.where(vig, GAIT_STOP, self.gait).astype(np.int8)
        self.vel = v
        self.vigilant = vig
        return v

    def _threat_flee_term(self) -> np.ndarray:
        """10절 #18 조향 변형 항 (N,2). `step` 1) 에서 threat_flee > 0 일 때만 `steer` 의 정규화 전 합에 더한다.

        결정 관측(이전 스텝 끝 8b)에서 포식자가 안 보인 개체: threat_flee · flee_weight · threat_recency · (−ThreatDir).
        보인 개체는 0 이다(v1 도주 항 `d_pred < flee_dist·see_r` 이 맡는다). 위협을 본 적 없으면 ThreatDir = 0 이라 0.
        threat_recency 가 감쇠하므로 놓친 직후에 크고(최대 flee_weight 배) 시간이 지나면 줄어든다. 구간과 무관하게
        안 보인 모든 개체에 걸린다(threat_recency < θ 인 평시 개체에도 θ·flee_weight 이하로 남는다).
        계약 밖의 시험 항이다(#18 '넣지 않고 시작한다'). Gate E2b 의 '계속 뛰기' 변형 팔에만 켜고, 크게 이기면 조향
        계약 변경안에 올린다. C++ 꼴: if (PredCount == 0) V += ThreatFlee * FleeWeight * Recency * (-ThreatDir);
        """
        unseen = self._g["pred_count"] == 0
        k = self._vg["threat_flee"] * self.cfg.flee_weight
        return np.where(unseen[:, None], (-k) * self.threat[:, None] * self.threat_dir, 0.0)

    def _face_threat(self) -> None:
        """경계한 개체의 heading ← ThreatDir (0 이면 유지), 시선 훅 갱신. `step` 1e) 와 8c) (`_vigil_step` docstring)."""
        face = self.vigilant & (self.threat_dir != 0.0).any(1)
        self.head[face] = self.threat_dir[face]
        self.gaze = self.head.copy()

    def _look_back(self) -> None:
        """v2.2r L 반사 돌아보기 (수정 제안서 3.1 (나), R2). `step` 1f) — 이동·heading 갱신(1d)과 경계 돌아보기(1e) 뒤.

        조건: 결정 때 창 안(`self.window`, `step` 0) & 이번 스텝의 실제 보행이 정지(`self.gait`, 경계 포함) & ThreatDir ≠ 0.
        그러면 heading ← ThreatDir(마지막 위협 방향, 단위벡터). 섭식·대사·시야는 정지 그대로다(섭식 gait_eat[정지],
        대사 c_rest, 다음 관측 기본 FOV). 그래서 이득은 돌아보기 하나 — 다음 관측(8)의 120° 시야가 놓친 포식자 쪽을
        향한다. 멈출지는 RL 이 speed 로 고른다(창 밖에서 멈춰도 반사가 없고, 상수 정책은 창 안에서만 멈출 수 없다).
        정지 개체는 v = 0 이라 1d 가 heading 을 바꾸지 않으므로 이 반사가 스텝 끝 heading 이다. 포식자는 heading 을
        보지 않는다(v1 그대로).
        C++ 꼴 (SteerV2, 이동 뒤): if (bWindow && Gait == Stop && !ThreatDir.IsZero()) Facing = ThreatDir;
               bWindow = (PredCount == 0 && Recency > Theta)  — 결정 관측 기준.
        스텝 뒤 훅(replay_v2): `self.looked`(반사가 돈 개체), `self.gaze`(스텝 뒤 heading).
        """
        face = self.window & (self.gait == GAIT_STOP) & (self.threat_dir != 0.0).any(1)
        self.head[face] = self.threat_dir[face]
        self.looked = face
        self.gaze = self.head.copy()

    def _gait_step(self, v: np.ndarray, a_speed: np.ndarray) -> np.ndarray:
        """v2.1 보행 (계획서 4.3·4.4). `step` 1) 에서 v1 조향 속도 `v`(크기 herb_speed 또는 0)의 크기만 바꾼다.

        한 스텝 순서 — C++ 로 옮길 때 이 순서를 지킨다. 상태가 없다(이전 스텝의 보행을 읽지 않는다):
          1a) 명령 보행 cmd = [a ≥ t_walk] + [a ≥ t_run] (0 정지, 1 걷기, 2 뛰기). a 는 sigmoid 뒤 [0,1] 값이고
              문턱은 고정값이다(최소 유지 시간 K 없음, #3)
          1b) 실제 보행 g = cmd. 단 조향 합의 방향이 없으면(|v| ≤ EPS, v1 의 '안 움직임' 판정과 같다) g = 정지.
              갈 방향이 없는 '걷기'는 제자리에 서 있는 것이므로 섭식·대사도 정지로 친다
          1c) v ← v × gait_speed[g]. 조향 방향 계산(steering.py)은 그대로다. 뛰기 1.0 이면 v1 속도와 비트 단위로 같다
          1d) (step) pos ← clip(pos + v, 0, size), |v| > EPS 면 heading ← v 방향, 아니면 유지 — v1 과 같은 줄이다.
              정지는 v = 0 이라 heading 을 유지한다. 벽에 막혀 실제 이동이 짧아도 대사는 보행 상태의 속력으로 낸다
              (clamp 전 v 로 heading 을 정하는 v1 과 같은 기준)
          2)  (step) 포식자 — v1 그대로
          3a) (step) 대사 drain = energy_drain × drain_mult[g], drain_mult = c_rest + c_move·gait_speed²
              (계획서 drain = energy_drain·(c_rest + c_move·(v/herb_speed)²) 에서 v/herb_speed = gait_speed[g])
          3b) (step) 섭식 want ← clip((max − e_drained)/fepu, 0, food_eat_rate) × gait_eat[g] (`_eat`), 나머지 v1
          3c) (step) 에너지 보상: net_energy_reward 면 e_new − e_prev, 아니면 v1 획득량 e_new − e_drained.
              번식 리셋(4)·리스폰(8)은 그 뒤라 순변화에 들어가지 않는다
        C++ 꼴 (V = v1 조향 합을 정규화해 HerbSpeed 를 곱한 값, 지금 SteeringProcessor 의 Velocity):
                Cmd = (A >= TWalk) + (A >= TRun); G = (V.SizeSquared() > EPS * EPS) ? Cmd : Stop;
                Velocity = V * GaitSpeed[G]; Drain = EnergyDrain * DrainMult[G]; Want *= GaitEat[G].
        스텝 뒤 훅(replay_v2): `self.gait` 실제 보행, `self.gait_cmd` 명령 보행, `self.vel` 적용 속도(벽 clamp 전).
        """
        sp = self._sp
        t_walk, t_run = sp["thresholds"]
        cmd = (a_speed >= t_walk).view(np.int8) + (a_speed >= t_run).view(np.int8)
        # |v| > EPS ⇔ v·v > EPS². steer 의 v 는 0 이거나 크기 herb_speed 라 경계 근처 값이 없다. 정지 = 0 이라 곱으로 고른다
        g = cmd * ((v * v).sum(1) > EPS * EPS)
        v = v * sp["speed"][g][:, None]
        self.gait, self.gait_cmd, self.vel = g, cmd, v
        return v

    def _rep_decision_obs(self) -> dict:
        """`repertoire.arbitrate` 의 결정 때 입력 (repertoire docstring A '결정 때 관측(이전 스텝 끝 기하)'): 지금 기하
        `self._g`(리스폰 관측 포함)의 포식자 수·가장 가까운 거리·접근 속력·사건 비교 시야 값·은신처와 지금 에너지(max_energy
        비율)·어둠. `_rep_step`(실제 결정)과 `rep_peek`(미리 보기)가 같은 이 함수를 써서 두 입력이 늘 같다."""
        g = self._g
        out = dict(pred_count=g["pred_count"], d_pred_min=g["d_pred_min"], pred_approach=g["pred_approach"],
                   pred_count_ev=g["pred_count_ev"], d_pred_min_ev=g["d_pred_min_ev"],
                   pred_approach_ev=g["pred_approach_ev"],
                   energy=np.clip(self.energy / self.cfg.max_energy, 0.0, 1.0), dark=self.dark,
                   in_cover=g["in_cover"], cover_k=g["cover_k"])
        if self._al is not None:        # v3 R2 M8: 지난 E′ 의 새·더 센 경보 → 사건 E7 (미리 보기와 실제 결정이 같은 입력)
            out["alarm_new"] = self._rs.alarm_new
        return out

    def rep_peek(self) -> dict:
        """다음 `step` 의 `arbitrate` 가 요청을 읽는지 미리 본다 (R1 명세 `Docs/RL_Policy/RL_V3_R1_SPEC.md` 2절 '결정').
        순수 함수다 — 행동 상태(RepState)를 복사해 같은 결정 때 입력(`_rep_decision_obs`)으로 `arbitrate` 를 돌려 보고 버린다.
        세계 상태와 난수를 건드리지 않으므로 부르든 부르지 않든 궤적이 비트 단위로 같다(tests/test_rep_policy_v3.py).

        반환 (모두 (N,) 사본):
          - reads: 요청을 읽는 개체 = 결정 시점((lock_left ≤ 0 또는 사건 fire) & 기상 중 아님 & 이번 스텝에 깨지 않음) 또는
            기상 결정(이번 스텝에 깨고 wake_ev 가 있음). `arbitrate` 반환의 decide 와 같은 값이다
          - wake_decide: 기상 결정인 개체(기상 결정의 SLEEP 요청은 wake_target 으로 바뀌므로 마스크가 SLEEP 을 막는다)
          - behavior: 지금 행동(int64, 결정 전 — 관측 obs_extra 의 행동 one-hot 과 같은 값)
        `decide` 는 요청 값과 무관하므로(잠금·사건·기상만 본다) 미리 보기의 요청은 지금 행동으로 둔다.
        """
        if self._rp is None:
            raise ValueError("rep_peek 은 repertoire 를 켠 세계에만 있다")
        rs = self._rs
        cp = object.__new__(rep.RepState)
        cp.__dict__.update({k: np.array(v, copy=True) for k, v in vars(rs).items()})
        woke = rs.waking & (rs.wake_left <= 0)          # arbitrate d. 의 woke 는 a~c 가 바꾸지 않는 칸만 본다
        res = rep.arbitrate(cp, self._rp, rs.behavior.astype(np.int64), self._rep_decision_obs())
        reads = np.asarray(res["decide"], dtype=bool).copy()
        return dict(reads=reads, wake_decide=reads & woke, behavior=rs.behavior.astype(np.int64))

    def _rep_step(self, a: np.ndarray) -> tuple[np.ndarray, dict]:
        """v3 행동 실행기 한 스텝 (`step` 0r·1r, 순서는 env_v2/repertoire.py docstring A·B). 반환: (적용 속도, 제어 결과).

        요청 = a[:, 0] 이고 0..4 의 정수 행동 번호여야 한다. 정수가 아니면 멈춘다 — 연속 정책(random [0, 1)·학습 정책의
        sigmoid (0, 1))을 내림하면 조용히 늘 GRAZE 가 되기 때문이다(random 은 `env_v2/rollout.adapt_spec` 이 정수 행동을 뽑는다).
        결정 때 입력은 이전 스텝 끝 기하 `self._g`(포식자 수·가장 가까운 거리·접근 속력·사건 비교 시야 값·은신처)와 결정 때
        에너지·어둠이다. GRAZE 의 '먹이 충분'은 결정 때 위치 셀의 먹이(섭식 전) ≥ graze_eat_min 이다. HIDE 는 고른 은신처의
        중심 쪽으로 간다(가장자리까지의 가장 가까운 점과 같은 방향).
        스텝 뒤 훅: `self.gait`(실제 보행, gait_cmd 도 같은 값 — 명령 보행이 없다), `self.vel`(적용 속도).
        """
        rp, rs, g, cfg = self._rp, self._rs, self._g, self.cfg
        req = a[:, 0]
        if (not np.all(np.isfinite(req)) or req.min() < 0 or req.max() >= rep.N_BEHAVIORS
                or not np.all(req == np.floor(req))):
            bad = req[~np.isfinite(req) | (req != np.floor(req))]
            raise ValueError(f"행동 'behavior' 는 0..{rep.N_BEHAVIORS - 1} 의 정수 행동 번호여야 한다(내림하지 않는다 — "
                             f"연속 정책 출력은 이 세계에 쓸 수 없다). 받은 범위: [{req.min()}, {req.max()}]"
                             + (f", 정수가 아닌 값 예: {bad[:3].tolist()}" if len(bad) else ""))
        prev = rs.behavior.copy()
        req_i = req.astype(np.int64)
        wf = self._wf
        if wf is not None:
            # 야생 (w3) 덮기: 도주 = FLEE, 웅크림 = HIDE 를 두뇌 요청 대신 넣는다(결정 시점이면 arbitrate 가 그대로 들어간다)
            mode = self.wf_mode
            req_i = np.where(mode == WF_PANIC, rep.FLEE, np.where(mode == WF_SHELTER, rep.HIDE, req_i))
        dobs = self._rep_decision_obs()
        res = rep.arbitrate(rs, rp, req_i, dobs)
        if wf is not None:
            self._wf_commit(res, dobs)
        ix, iy = self._cell_index(self.pos)
        to_target = np.zeros((self.N, 2))
        m = (rs.behavior == rep.HIDE) & ~rs.arrived & (rs.hide_target >= 0)
        if m.any():
            to_target[m] = normalize(self.cov_c[rs.hide_target[m]] - self.pos[m])
        inp = dict(food_grad=g["food_grad"], to_centroid=g["to_centroid"], separation=g["separation"],
                   away_from_pred=g["away_from_pred"], to_target=to_target, pred_count=g["pred_count"],
                   food_ok=self.food[iy, ix] >= rp["graze_eat_min"], in_cover=g["in_cover"], dark=self.dark)
        if wf is not None:
            # 야생 (w3) 도주: FLEE 제어기의 위협 반대 방향 = 덮기 방향(보인 위협으로 둔다 — C++ KeepControl 과 같은 꼴)
            pan = (self.wf_mode == WF_PANIC) & (self.wf_dir != 0.0).any(1)
            if pan.any():
                inp["away_from_pred"] = np.where(pan[:, None], self.wf_dir, g["away_from_pred"])
                inp["pred_count"] = np.where(pan, np.maximum(g["pred_count"], 1), g["pred_count"])
        out = rep.control(rs, rp, inp, cfg, self._sp)
        if wf is not None:
            self._wf_alert_control(out, inp)
        self.gait, self.gait_cmd, self.vel = out["gait"], out["gait"].copy(), out["vel"]
        self._rep_eat, self._rep_drain = out["eat"], out["drain"]
        self._rep_see_last = self._rep_see                  # 결정 관측(self._g)을 만든 배수 → 다음 관측의 '직전' 배수
        self._rep_see, self._rep_still = out["see"], out["still"]
        self._rep_crouch = out["crouch"]
        # M6 행동별 은신 배수(은신처 안일 때): 웅크린 HIDE, GRAZE, SLEEP, 그 밖 (repertoire.cover_mult)
        self._rep_cover = rep.cover_mult(rp, rs.behavior, out["crouch"])
        out.update(res)
        out["prev"] = prev
        return out["vel"], out

    def _alarm_emit_step(self, rep_out: dict) -> None:
        """v3 R2 M8 A′ (env_v2/repertoire.py docstring A′, `repertoire.alarm_emit`): arbitrate 의 전환과 결정 관측(이전 스텝 끝
        기하 self._g, 결정 때 위치)으로 이번 스텝 방출 목록을 만들고 alarm_new 를 끈다. 훅 alarm_e7 과 E7·진입·물결·헛경보
        통계를 센다(동역학과 무관). 비명은 포획 뒤 `_alarm_cry` 가, 받기는 E′ `_alarm_receive_step` 이 한다."""
        rs, al, g, t = self._rs, self._al, self._g, self.t
        em = rep.alarm_emit(rs, al, rep_out["switch"], g["pred_count"], self.pos, g["away_from_pred"], g["d_pred_min"], t)
        em["src_j"] = np.where(em["emit"] & em["seen"], g["pred_j"], -1)
        self._al_em = em
        e7, sw = rep_out["e7"], rep_out["switch"]
        self.alarm_e7 = e7.copy()
        # 통계: E7 → 결정 지연 창 안의 전환, 행동별 진입·'들음' 진입, 물결 크기(같은 원점의 들은 진입), 헛경보
        self._al_e7_n += int(np.count_nonzero(e7))
        self._al_e7_t[e7] = t
        self._al_e7_dt[e7] = t
        if sw.any():
            hit = sw & (t - self._al_e7_t <= self._rp["decision_jitter"])
            self._al_e7_sw += int(np.count_nonzero(hit))
            self._al_e7_t[hit] = -(10 ** 9)
        dec = np.asarray(rep_out["decide"], dtype=bool)
        if dec.any():                   # 글자 그대로 판: E7 뒤 지연 창 안에 결정 시점이 왔다(행동을 유지한 결정 포함)
            hit = dec & (t - self._al_e7_dt <= self._rp["decision_jitter"])
            self._al_e7_dn += int(np.count_nonzero(hit))
            self._al_e7_dt[hit] = -(10 ** 9)
        into = em["into"]
        if into.any():
            cause = rs.entry_cause
            heard = into & ((cause & rep.ENTRY_HEARD) > 0) & ((cause & rep.ENTRY_SEEN) == 0)
            b = rs.behavior.astype(np.int64)
            self._al_entry += np.bincount(b[into], minlength=rep.N_BEHAVIORS)
            self._al_entry_heard += np.bincount(b[heard], minlength=rep.N_BEHAVIORS)
            wave = heard & (self._al_src >= 0) & (t - rs.al_t0 <= WAVE_STEPS) & (self._al_wave_last != self._al_src)
            self._al_wave_hits += int(np.count_nonzero(wave))
            self._al_wave_last[wave] = self._al_src[wave]
        sj = em["src_j"]
        seen0 = sj >= 0
        if seen0.any():
            self._al_seen0 += int(np.count_nonzero(seen0))
            self._al_false += int(np.count_nonzero(~self._pred_active[sj[seen0]]))

    def _alarm_cry(self, caught: np.ndarray) -> None:
        """v3 R2 M8 비명 (on_catch): 이번 스텝에 잡힌 개체는 홉 0 으로 낸다. 점 = 잡은 위협의 위치(이동 뒤, 동시 포획이면 낮은
        번호 위협 = 위협 슬롯 순서), t0 = t. 같은 스텝의 전환 방출을 덮는다 — 개체 키 하나에 방출 항목은 늘 하나다(같은 키의 홉 0
        두 개가 버퍼에 남으면 (홉, 거리², 키) 사전식 최소로 고를 수 없다). alarm_seq 는 한 번만 + 1. 위치는 E′ 에서 스텝 끝 위치
        (잡힌 자리, 리스폰 전)로 채운다. C++ 꼴 (EcoKinAlarm.h, 포획 뒤):
          if (OnCatch) EmitOrReplace(VictimKey, {0, Q[CatcherSlot], T});   // 같은 키의 전환 방출을 덮는다, Seq 는 한 번만 +1
          // CatcherSlot = 이번 스텝에 그 개체를 잡은 위협 중 위협 슬롯 번호가 가장 작은 것(위협 배열의 안정 순서)"""
        em, c = self._al_em, np.flatnonzero(caught)
        em["emit"][c] = True
        em["hop"][c] = 0
        em["pt"][c] = self.pred_pos[self._caught_by[c]]
        em["t0"][c] = self.t
        em["cry"][c] = True
        em["src_j"][c] = -1

    def _alarm_receive_step(self, g: dict) -> None:
        """v3 R2 M8 E′ (env_v2/repertoire.py docstring E′, `repertoire.alarm_receive`): perceive 뒤·관측 전·리스폰 전에 경보를
        받고 스텝 뒤 훅을 정한다. 위치는 스텝 끝(이동 뒤, 리스폰 전), 동점 키는 AgentKey(슬롯·2^32 + 세대). 통계를 센다."""
        rs, al, em = self._rs, self._al, self._al_em
        ts = self.t - 1                                 # 이번 스텝 번호(self.t 는 이미 넘어갔다)
        N = self.N
        src_prev = self._al_src.copy()
        res = rep.alarm_receive(rs, al, em, self.pos, rep.agent_keys(np.arange(N), self._rep_gen), g["pred_count"])
        ei, emitted = res["src"], res["emitted"]
        # 훅 (애니메이션·리플레이 계약)
        self.alarm_level = rep.alarm_level(rs, al)
        self.alarm_hop = np.where(rs.al_ttl > 0, rs.al_hop, -1).astype(np.int64)
        self.alarm_seq = rs.alarm_seq.copy()
        self.alarm_pt = rs.al_pt.copy()
        self.alarm_emit = np.where(emitted, em["hop"], -1).astype(np.int64)
        self.entry_cause = rs.entry_cause.copy()
        self.alarm_from = np.where(res["accept"], res["best"], -1).astype(np.int64)
        # 통계: 방출·비명·방출당 청취, 원점(홉 0) 번호와 물결, 경보 개체-스텝, 간격, 방향 오차, 1초 안 고개 든 비율
        hop_e = em["hop"][ei]
        self._al_emit_n += np.bincount(np.minimum(hop_e, 2), minlength=3)[:3]
        self._al_cry += int(np.count_nonzero(em["cry"]))
        self._al_listen += int(res["listen"].sum())
        self._al_emitters += len(ei)
        esrc = np.full(N, -1, dtype=np.int64)
        h0 = ei[hop_e == 0]
        esrc[h0] = self._al_next_src + np.arange(len(h0))
        self._al_next_src += len(h0)
        self._al_h0 += len(h0)
        rel = ei[hop_e > 0]
        esrc[rel] = src_prev[rel]
        src = src_prev
        src[ei] = esrc[ei]
        acc = res["accept"]
        src[acc] = esrc[res["best"][acc]]
        self._al_src = src
        held = rs.al_ttl > 0
        self._al_with += int(np.count_nonzero(held))
        self._al_with_unseen += int(np.count_nonzero(held & (np.asarray(g["pred_count"]) == 0)))
        on = np.flatnonzero(res["onset"])
        if len(on):
            last = self._al_onset_t[on]
            ok = last >= 0
            self._al_gap_sum += int((ts - last[ok]).sum())
            self._al_gap_n += int(np.count_nonzero(ok))
            self._al_onset_t[on] = ts
        ds = np.flatnonzero(res["dirset"])
        if len(ds) and self.M > 0:
            awake = np.ones(self.M, dtype=bool) if self._ps is None else ~self.pred_asleep
            if awake.any():
                q = self.pred_pos[awake]
                P = self.pos[ds]
                dq = q[None, :, :] - P[:, None, :]
                near = dq[np.arange(len(ds)), np.argmin((dq * dq).sum(2), 1)]
                u = normalize(near)
                ok_pt = (normalize(rs.al_pt[ds] - P) * u).sum(1) >= DIR_COS
                ok_cp = (-rs.away[res["best"][ds]] * u).sum(1) >= DIR_COS
                self._al_dir_n += len(ds)
                self._al_dir_pt += int(np.count_nonzero(ok_pt))
                self._al_dir_cp += int(np.count_nonzero(ok_cp))
        due = [h for h in self._al_heads if h[0] == ts]
        if due:
            self._al_heads = [h for h in self._al_heads if h[0] != ts]
            b = rs.behavior
            for _, idx, gen, in_a, in_16 in due:
                ok = self._rep_gen[idx] == gen
                up = ok & ((b[idx] == rep.FREEZE) | (b[idx] == rep.FLEE))
                self._al_heads_n += int(np.count_nonzero(ok & in_a))
                self._al_heads_up += int(np.count_nonzero(up & in_a))
                self._al_heads16_n += int(np.count_nonzero(ok & in_16))
                self._al_heads16_up += int(np.count_nonzero(up & in_16))
        r16 = max(float(al["alarm_r"]), HEADS_UP_R16)
        for i in h0:                    # heads_up_1s 는 alarm_r 안, heads_up_1s_r16 은 16단위 안(사전 등록 5절 글자 그대로)
            d = np.sqrt(((self.pos - self.pos[i]) ** 2).sum(1))
            idx = np.flatnonzero(d <= r16)
            idx = idx[idx != i]
            if len(idx):
                self._al_heads.append((ts + HEADS_UP_STEPS, idx, self._rep_gen[idx].copy(), d[idx] <= al["alarm_r"],
                                       d[idx] <= HEADS_UP_R16))

    def _step_predators(self) -> np.ndarray:
        """포식자 2종 (§4.2). 은신처 안 초식은 거리가 `cover_hide_mult` 배로 보인다."""
        cfg = self.cfg
        if self.M == 0:
            return np.zeros(self.N, dtype=bool)

        ar = np.arange(self.M)
        dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]      # (M,N)
        dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        inv = 1.0 / np.maximum(dist, EPS)
        # 이번 스텝 이동 후 위치 기준. self._g는 이동 전 기하라 여기서 다시 판정한다.
        hide = np.where(self._in_cover(self.pos), cfg.cover_hide_mult, 1.0)[None, :]
        perceived = dist * hide
        self.pred_cd = np.maximum(self.pred_cd - 1, 0)
        hunting = self.pred_cd == 0
        if self._ps is not None:        # v2.4s: 자는 포식자는 사냥하지 않는다(쿨다운은 그대로 준다)
            hunting = hunting & ~self.pred_asleep
        vis = (
            (perceived <= cfg.pred_view_r)
            & (
                (dx * self.pred_head[:, 0:1] + dy * self.pred_head[:, 1:2]) * inv
                >= cfg.pred_fov_cos
            )
            & hunting[:, None]
        )

        # 추적: 시야 내 최근접(체감 거리 기준)
        masked = np.where(vis, perceived, np.inf)
        j = masked.argmin(1)
        has_target = np.isfinite(masked[ar, j])
        turn = self.rng.uniform(-cfg.pred_wander_turn, cfg.pred_wander_turn, self.M)
        c, s = np.cos(turn), np.sin(turn)
        wander = np.stack(
            [
                self.pred_head[:, 0] * c - self.pred_head[:, 1] * s,
                self.pred_head[:, 0] * s + self.pred_head[:, 1] * c,
            ],
            1,
        )
        chase = np.stack([dx[ar, j], dy[ar, j]], 1) * inv[ar, j][:, None]
        move = np.where(has_target[:, None], chase, wander)
        if self._ps is None:
            self.pred_pos = self.pred_pos + move * self.pred_speed[:, None]
        else:                           # v2.4s: 자는 포식자는 멈추고 방향을 유지한다. 깨어 있는 주행성은 박명 감속
            move = np.where(self.pred_asleep[:, None], self.pred_head, move)
            self.pred_pos = self.pred_pos + move * (self.pred_speed * self._pred_speed_mult)[:, None]
            self._ps_asleep_sum += float(self.pred_asleep.mean()) if self.M else 0.0
            self._ps_steps += 1
        # 벽에서 반사 (§4.2 토러스 끄기)
        for axis in (0, 1):
            out_of = (self.pred_pos[:, axis] < 0.0) | (self.pred_pos[:, axis] > self.size)
            move[out_of, axis] *= -1.0
        self.pred_pos = np.clip(self.pred_pos, 0.0, self.size)
        self.pred_head = normalize(move)

        # 포획: 근접형은 결정적, 원거리형은 확률적 (§4.2). 포식자당 한 스텝 한 마리.
        hit = (perceived <= self.pred_catch_r[:, None]) & hunting[:, None]
        if self.pred_ranged.any():
            roll = self.rng.random((self.M, self.N)) < cfg.pred_ranged_catch_p
            hit &= np.where(self.pred_ranged[:, None], roll, True)
        hit_d = np.where(hit, perceived, np.inf)
        k = hit_d.argmin(1)
        got = np.isfinite(hit_d[ar, k])
        caught = np.zeros(self.N, dtype=bool)
        caught[k[got]] = True
        self.pred_cd[got] = int(cfg.pred_eat_cd)
        return caught

    def _step_predators_v3(self) -> np.ndarray:
        """v3 포식자·위협 스텝 (repertoire·threats 중 하나라도 켠 세계, 명세 3절). `_step_predators` 와 같은 순서다:
        체감 거리 → 쿨다운 → 표적(시야 안 최근접 체감 거리) → 이동 → 벽 반사 → 포획(이동 전 거리, v1 그대로).

        - 체감 거리 (repertoire): 표적 선택 = 실거리 × max(은신 배수, still 이면 c_still)(M1·M6), 포획 = 실거리 × 은신 배수.
          은신 배수 = 은신처 안이면 행동별 값(웅크린 HIDE cover_mult_crouch, GRAZE cover_mult_graze, SLEEP cover_mult_sleep,
          그 밖 cover_mult_other — `repertoire.cover_mult`), 밖이면 1.
          repertoire 를 끈 세계는 v1 그대로 은신처 안 cover_hide_mult 를 둘 다에 쓴다.
        - 잠행형 (threats, M3): 배회 중 표적이 있고 체감 거리 > stalk_dist 면 stalk_speed 로 잠행, ≤ stalk_dist 면 돌진을
          시작한다(pounce_speed 로 pounce_steps 번 이동, 표적이 안 보이면 곧장). 돌진 이동을 다 쓴 다음 스텝이 마지막 포획
          판정이고(느리게 곧장), 놓치면 exhaust_steps 동안 탈진(exhaust_speed 로 배회, 사냥 안 함). 잡으면 배회로 돌아간다.
          자는 잠행형은 처음 상태로 돌아간다. 밤잠·박명 감속은 추격형과 같다.
        - 플레이어 (threats): 맵 전체를 본다(시야 반경·각 없음, 체감 거리는 같다 — 사람 플레이어는 화면의 모든 개체를 본다.
          그래서 정지·웅크림은 플레이어의 표적 순위만 바꾸고 표적에서 벗어나게 하지는 못한다. 명세의 '가장 가까운 무리'는
          '체감 거리가 가장 가까운 개체'로 둔다. 결정 기록은 results/v3/r0/PREREG.md 변경 기록). 배회(player_speeds[0], 선회는
          자기 스트림 part 3) · 잠행(player_speeds[1], 가장 가까운 개체 쪽, 체감 거리 ≤ player_charge_dist 면 돌진 시작) · 돌진
          (player_speeds[2] 로 player_charge_steps 번, 마지막 판정 뒤 휴식) · 휴식(멈춤, 사냥 안 함, player_rest_steps).
          배회·잠행 모드 길이가 끝나거나 휴식이 끝나면 모드를 새로 고른다(`_player_new_mode`). 포획 뒤 쿨다운 player_cooldown.
          밤에 자지 않는다.
        - v1 스트림: 배회 선회 M_base 개, v1 원거리형 배치에 원거리형이 있으면 원거리 판정 (M_base, N) 개 — v2.4s 와 같은 모양
          (플레이어 몫은 threats 스트림, 잠행형이 덮은 원거리형의 판정은 쓰지 않는다).
        - v3 R2 M7 (stare_down, 명세 2-5): 1 실거리·체감 거리 → 2 쿨다운·사냥 가능, 자는 잠행형 초기화(잠금·spot_cnt·대치·물러남
          포함) → 3·4 `_stare_check`(잠금 확인, 노려보기 → 대치·물러남·들킴) → 5 탈진·휴식·대치·물러남을 사냥에서 뺀다 → 6 표적
          선택 뒤 `_stare_target`(잠금 덮기) → 7 배회 선회 난수(대치·물러남도 뽑는다, 모양 그대로) → 8 `_threat_motion`(돌진
          시작은 잠금을 지움, 들킨 돌진, 대치 속력 0·표적 쪽, 물러남) → 9 밤잠·박명 감속(물러남 속력에도) → 10 이동·벽 반사(balk_dir
          도) → 11 포획(대치·물러남은 잡지 않는다, 잡은 위협의 잠금을 지움, `_stare_after`) → 12 `_threat_after`(물러남·들킴 남은
          스텝, 돌진이 끝나면 들킨 돌진 표시를 지움). 대치가 깨지면 4 에서 배회가 되어 같은 스텝의 6~8 을 그대로 탄다.
        - v3 R3 (j) 늑대 먹는 시간 (threats.eat_in_place, 10-15): 상태 기계·추격 고정 뒤, 밤잠 배수 앞에서 쿨다운이 남은 늑대(플레이어형
          위협 제외)의 속력을 0, 방향을 heading 그대로 둔다(모듈 docstring 'R3 세계' (j)).
        스텝 뒤 훅: `self.pred_vel`(이번 스텝 실제 이동, 관측 pred_approach).
        """
        cfg, th, rp, sd = self.cfg, self._th, self._rp, self._sd
        M, Mb, N = self.M, self.M_base, self.N
        if M == 0:
            return np.zeros(N, dtype=bool)
        ar = np.arange(M)
        old = self.pred_pos.copy()
        dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]      # (M,N)
        dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        inv = 1.0 / np.maximum(dist, EPS)
        in_cov = self._in_cover(self.pos)
        if rp is not None:
            cov = np.where(in_cov, self._rep_cover, 1.0)
            det = np.maximum(cov, np.where(self._rep_still, rp["c_still"], 1.0))
        else:
            cov = det = np.where(in_cov, cfg.cover_hide_mult, 1.0)
        perceived = dist * det[None, :]
        catch_d = dist * cov[None, :]
        safe_m = None
        if self._zs is not None:
            # v3 현실성 (c): 은신처 원 안(이번 스텝 초식 이동 뒤 위치 — 포획 판정과 같은 정의)이면 행동과 무관하게 안전. player_too 가
            # 아니면 플레이어 칸은 지금 그대로다. 안전 (M,N) 은 표적·잠금(_stare_check)·포획 판정이 함께 쓴다
            safe_m = np.broadcast_to(in_cov[None, :], (M, N))
            if th is not None and not self._zs["player_too"]:
                safe_m = safe_m & ~self.pred_is_player[:, None]
            self._zs_safe_m = safe_m
            self._zs_safe_n += int(np.count_nonzero(in_cov))
            self._zs_steps += N
        self.pred_cd = np.maximum(self.pred_cd - 1, 0)
        hunting = self.pred_cd == 0
        sated = None
        if self._ws is not None:
            # 야생 (w2) 포만: 먹기(쿨다운)가 끝났고 배부름이 남은 늑대는 이번 스텝 사냥하지 않고 쉰다(남은 스텝 −1). 플레이어형 위협은 pred_sat 이 늘 0
            sated = (self.pred_cd == 0) & (self.pred_sat > 0)
            self.pred_sat = np.where(sated, self.pred_sat - 1, self.pred_sat)
            self.pred_sated = sated
            hunting = hunting & ~sated
            self._ws_sated_n += int(np.count_nonzero(sated[:Mb]))
            self._ws_eat_n += int(np.count_nonzero(self.pred_cd[:Mb] > 0))
            self._ws_steps_n += Mb
        if self._ps is not None:
            hunting = hunting & ~self.pred_asleep
        if self._zn is not None and self.dark >= self._zn["hunt_dark"]:
            # v3 현실성 (d): 깜깜하면(결정 때 어둠 d ≥ hunt_dark) 주행성 늑대는 새 사냥을 시작하지 않는다 — 지난 포식자 스텝에 사냥
            # 중이던 늑대만 계속 쫓는다(표적·포획 모두). 야행성·플레이어는 그대로다
            hunting = hunting & (self.pred_nocturnal | self._zn_hunt)
        ts = None
        if th is not None:
            stalker = self.pred_type == PT_STALKER
            if self._ps is not None:
                zz = stalker & self.pred_asleep
                self.stalk_state[zz] = ST_ROAM
                self.stalk_left[zz] = 0
                if sd is not None:      # v3 R2: 잠드는 잠행형은 잠금·spot_cnt 도 초기화한다(대치·물러남은 위에서 배회로)
                    self.pred_lock[zz] = -1
                    self.spot_cnt[zz] = 0
            exh0 = stalker & (self.stalk_state == ST_EXHAUST)
            rest0 = self.pred_is_player & (self.player_mode == PM_REST)
            if sd is not None:          # v3 R2 C0: 잠금 확인·노려보기(대치·물러남·들킴). 대치·물러남은 사냥하지 않는다
                self._stare_check(dx, dy, dist, inv, perceived, hunting)
                st = self.stalk_state
                hunting = hunting & ~(stalker & ((st == ST_STANDOFF) | (st == ST_BALK)))
            hunting = hunting & ~exh0 & ~rest0
        zc = self._zc
        if zc is not None:              # v3 R3 (f) 1): 고정한 표적 놓기·시야 갱신(사냥 가능을 정한 뒤, 표적 고르기 전)
            self._rz_chase_release(dist, dx, dy, inv, in_cov, hunting)
        vis = (perceived <= cfg.pred_view_r) & (
            (dx * self.pred_head[:, 0:1] + dy * self.pred_head[:, 1:2]) * inv >= cfg.pred_fov_cos)
        if self._ob is not None and self._ob["block_sight"] and len(self.obstacles):
            # 야생 2단계 3 의 3): 늑대 눈길도 원판이 가린다(플레이어형 위협은 아래에서 늘 본다)
            vis, n_pair, n_blk = self._ob_occlude(vis, self.pred_pos, self.pos)
            self._ob_tgt_pairs += n_pair
            self._ob_tgt_blocked += n_blk
        if th is not None and M > Mb:
            vis[self.pred_is_player] = True
        vis &= hunting[:, None]
        if self.alive is not None:
            vis[:, ~self.alive] = False     # 통합 무대 (k): 시체는 표적이 아니다(C++ Prey 는 산 사슴 목록 — 지난 스텝에 죽은 개체가 빠진다)
        if safe_m is not None and self._zs["untargetable"]:
            vis &= ~safe_m              # v3 현실성 (c): 안전한 사슴은 표적이 되지 않는다(위협 m 별 — player_too 가 아니면 플레이어는 그대로)
        masked = np.where(vis, perceived, np.inf)
        j = masked.argmin(1)
        d_t = masked[ar, j]
        has_target = np.isfinite(d_t)
        if sd is not None:              # v3 R2 M7a: 사냥 중인 잠행 위협은 잠긴 표적을 쫓고, 잠금이 없으면 고른 표적을 잠근다
            j, d_t, has_target = self._stare_target(j, d_t, has_target, hunting, perceived)
        if zc is not None:              # v3 R3 (f) 3): 쥔 위협은 고정한 표적을 쫓는다(안 보이면 마지막으로 본 자리로)
            j, d_t, has_target, chase_lost = self._rz_chase_target(j, d_t, has_target, dist)
        turn = self.rng.uniform(-cfg.pred_wander_turn, cfg.pred_wander_turn, Mb)
        if M > Mb:
            turn = np.concatenate([turn, self.feature_rng("threats", 3).uniform(
                -cfg.pred_wander_turn, cfg.pred_wander_turn, M - Mb)])
        c, s = np.cos(turn), np.sin(turn)
        wander = np.stack([self.pred_head[:, 0] * c - self.pred_head[:, 1] * s,
                           self.pred_head[:, 0] * s + self.pred_head[:, 1] * c], 1)
        chase = np.stack([dx[ar, j], dy[ar, j]], 1) * inv[ar, j][:, None]
        if zc is not None and chase_lost.any():
            # 고정한 표적이 시야 밖: 마지막으로 본 자리 쪽(그 자리에 닿았으면 지금 heading). C++ 꼴: SafeDir(LastSeen − Q, H)
            v = self.chase_pt[chase_lost] - self.pred_pos[chase_lost]
            n = np.sqrt((v * v).sum(1))
            chase[chase_lost] = np.where((n > EPS)[:, None], v / np.maximum(n, EPS)[:, None], self.pred_head[chase_lost])
        move = np.where(has_target[:, None], chase, wander)
        speed = self.pred_speed.copy()
        if th is not None:
            st0 = self.stalk_state.copy() if self._zt is not None else None
            move, speed, ts = self._threat_motion(move, speed, wander, has_target, d_t, exh0, rest0)
            if st0 is not None:         # v3 R3 (h) 통계 전용: 돌진을 시작한 잠행형의 돌진 표적 사슴이 선 땅(포획 판정 때 다시 쓴다)
                started = stalker & (st0 == ST_ROAM) & (self.stalk_state == ST_POUNCE)
                if started.any():
                    tc = self._rz_terrain_of(self.pos[j[started]])
                    self._zt_pounce_tc[started] = tc
                    self._zt_pounce += np.bincount(tc, minlength=len(TERRAIN_NAMES))
        if zc is not None:              # v3 R3 (f) 4): 상태 전이 뒤 새 고정(돌진을 막 시작한 잠행형은 돌진 표적)
            self._rz_chase_acquire(j, has_target, hunting)
        if self._wp is not None:        # 야생 2단계 2: 돕는 늑대는 배회 대신 쫓기는 사슴이 달아날 곳으로 가서 기다린다(먹기·배부름·밤잠 배수 앞)
            move, speed = self._pack_step(move, speed, has_target, j, hunting)
        if self._eat_in_place:
            # v3 R3 (j) 늑대 먹는 시간(10-15): 잡은 뒤 쿨다운이 남은 늑대(플레이어형 위협 말고 모든 포식자)는 그 자리에 서서 먹는다 —
            # 속력 0, heading 그대로(자는 늑대와 같은 꼴). 쿨다운은 이 스텝 첫머리에 이미 1 줄었으므로 cd > 0 이면 이번 스텝은 사냥하지
            # 않는다(표적·포획 없음). 배회 선회 난수는 위에서 그대로 뽑았다(v1 스트림 모양 그대로). C++ 꼴:
            #   if (bEatInPlace && Type != Player && Cooldown > 0) { Move = Head; Speed = 0; }
            eating = (self.pred_cd > 0) & ~self.pred_is_player
            if eating.any():
                move = np.where(eating[:, None], self.pred_head, move)
                speed = np.where(eating, 0.0, speed)
        if sated is not None and sated.any():
            # 야생 (w2): 배부른 늑대는 느리게 어슬렁거린다(배회 방향 그대로 — 표적이 없으므로 move 는 배회다). 밤잠 배수 앞. C++ 꼴: Speed *= RestSpeed
            speed = np.where(sated, speed * self._ws["rest_speed"], speed)
        if self._ps is not None:
            move = np.where(self.pred_asleep[:, None], self.pred_head, move)
            speed = speed * self._pred_speed_mult
            self._ps_asleep_sum += float(self.pred_asleep[:Mb].mean()) if Mb else 0.0
            self._ps_steps += 1
        if self._zt is not None:
            # v3 R3 (h): 이동 전 위치 셀의 땅 배수 — 밤잠 배수 다음에 곱한다(곱 순서 (속력 × 밤 배수) × 땅 배수, C++ 와 같게).
            # 플레이어형 위협은 mult_player
            tc = self._rz_terrain_of(self.pred_pos)
            tm = self._zt["mult_pred"][tc]
            if th is not None and M > Mb:
                tm = np.where(self.pred_is_player, self._zt["mult_player"][tc], tm)
            speed = speed * tm
        self.pred_pos = self.pred_pos + move * speed[:, None]
        ob_on = self._ob is not None and len(self.obstacles) > 0
        if ob_on:
            # 야생 2단계 3 의 2): 원판 앞에서 멈춰 둘레를 따라 미끄러진다(은신처 밀어내기·벽 반사 앞). 원 안 되돌림·막다른 곳은 아래 끝에서
            ob_step = move * speed[:, None]
            self.pred_pos, ob_hit, _ = obstacle_slide(old, self.pred_pos, self.obstacles, self._ob["body_r"])
        if self._zw:                    # v3 R3 (c′): 은신처 원 안으로 들어간 막는 위협을 둘레 밖으로(벽 반사 전)
            step_v = move * speed[:, None]                  # 이번 스텝 이동(접선 미끄러짐 되돌림에 쓴다, 벽 반사 전 방향)
            self.pred_pos, wpushed = self._rz_wall_push(self.pred_pos, old, self._zw_sel)
            self._zw_push_n += int(np.count_nonzero(wpushed))
        balk = (stalker & (self.stalk_state == ST_BALK)) if sd is not None else None
        wall_b = np.zeros(M, dtype=bool)
        for axis in (0, 1):
            out_of = (self.pred_pos[:, axis] < 0.0) | (self.pred_pos[:, axis] > self.size)
            move[out_of, axis] *= -1.0
            if balk is not None:
                # v3 R2 (사람 결정 10-12): 물러나다 벽에 닿으면 반사하지 않고 벽을 따라 미끄러진다 — 벽에 수직인 성분을 없앤다.
                # 반사하면 물러남의 절반 가까이가 표적 쪽으로 되돌아와 포식자 시야 안에서 끝났다(구현 검토 10-12)
                ob = out_of & balk
                self.balk_dir[ob, axis] = 0.0
                wall_b |= ob
        if wall_b.any():
            # 남은 성분(벽을 따라, 원래 물러남 방향 = 표적에서 멀어지는 쪽)으로 다시 단위화한다. 표적 쪽으로 곧장 벽에 박혀
            # 남은 성분이 없으면(또는 모서리) 맵 가운데 쪽 벽 방향으로 간다. 난수 없음. C++ 꼴:
            #   if (bBalk && bHitWall[a]) BalkDir[a] = 0;
            #   BalkDir = BalkDir.Size() > EPS ? BalkDir.GetSafeNormal() : WallTangentToCenter(Pos);
            bd = self.balk_dir[wall_b]
            n = np.sqrt((bd * bd).sum(1))
            p = self.pred_pos[wall_b]
            to_c = np.where(p <= 0.5 * self.size, 1.0, -1.0)            # 축마다 가운데 쪽 부호
            hit_x = (p[:, 0] <= 0.0) | (p[:, 0] >= self.size)
            hit_y = (p[:, 1] <= 0.0) | (p[:, 1] >= self.size)
            tang = np.stack([np.where(hit_x, 0.0, to_c[:, 0]), np.where(hit_y, 0.0, to_c[:, 1])], 1)
            tn = np.sqrt((tang * tang).sum(1))
            tang = np.where((tn > EPS)[:, None], tang / np.maximum(tn, EPS)[:, None], to_c / np.sqrt(2.0))
            self.balk_dir[wall_b] = np.where((n > EPS)[:, None], bd / np.maximum(n, EPS)[:, None], tang)
            move[wall_b] = self.balk_dir[wall_b]
        self.pred_pos = np.clip(self.pred_pos, 0.0, self.size)
        if self._zw:
            # v3 R3 (c′): 밀어내도(또는 벽 clip 뒤에) 은신처 원 안이면 — 원이 맵 가장자리에 걸쳐 밀어낸 자리가 맵 밖이었거나 겹친 원 —
            # 이전 위치에서 가장 가까운 원의 접선 방향으로만 간다(안쪽 성분만 뺀 이동, 맵 안으로 자름). 그래도 원 안이면 이전 위치(늘 원
            # 밖)에 남는다
            inside = self._zw_sel & self._rz_inside_disc(self.pred_pos)
            if inside.any():
                alt = self._rz_wall_tangent(old[inside], step_v[inside])
                ok = ~self._rz_inside_disc(alt)
                self.pred_pos[inside] = np.where(ok[:, None], alt, old[inside])
                self._zw_slide_n += int(np.count_nonzero(ok))
            # 막다른 곳(원에 막혀 이번 스텝에 가려던 거리의 WALL_DEAD_FRAC 도 못 감 — 원과 맵 가장자리 사이 구석, 겹친 두 원 사이의 V 자
            # 틈, 원 중심 쪽으로 곧장 부딪힘)이면 돌아선다(heading ← 이번 이동의 반대 방향) — 맵 벽에서 튕기는 것과 같은 꼴. 그러지 않으면
            # 늑대가 구석을 계속 파고들어 수백 스텝 멈춘다(보정 시드 20001·20004 점검: 783·279 스텝). 돌아선 추격형은 원 너머 표적이 시야
            # 밖이 되어 놓는다(닿을 수 없는 먹잇감을 포기). C++ 꼴:
            #   if (bBlocked && |V| > Eps && |Q - P| < WallDeadFrac * |V|) Move = -V / |V|;
            want = np.sqrt((step_v * step_v).sum(1))
            dv = self.pred_pos - old
            dead = (wpushed | inside) & (want > EPS) & (np.sqrt((dv * dv).sum(1)) < WALL_DEAD_FRAC * want)
            if dead.any():
                move[dead] = -step_v[dead] / want[dead][:, None]
                self._zw_stuck_n += int(np.count_nonzero(dead))
                if th is not None and M > Mb:
                    # 플레이어형 위협은 맵 전체를 봐서 돌아서도 다음 스텝에 같은 사슴 쪽으로 되돌아온다(V 자 틈에 잠행 모드 내내 끼인다,
                    # 탐색 시드 32018). 표적이 있으면 그 접근을 그만둔다: 잠행 → 배회(남은 길이 그대로), 돌진 → 남은 돌진 0(이번 스텝
                    # 포획 판정 뒤 `_threat_after` 가 휴식으로). 난수 없음. C++ 꼴:
                    #   if (bDead && Type==Player && bHasTarget) { if (Mode==Stalk) Mode = Wander; else if (Mode==Charge) PlayerLeft = 0; }
                    gp = dead & self.pred_is_player & has_target
                    if gp.any():
                        stalk_p = gp & (self.player_mode == PM_STALK)
                        charge_p = gp & (self.player_mode == PM_CHARGE)
                        self.player_mode[stalk_p] = PM_WANDER
                        self.player_left[charge_p] = 0
                        self._zw_giveup_n += int(np.count_nonzero(stalk_p | charge_p))
            self._zw_inside_n += int(np.count_nonzero(self._zw_sel & self._rz_inside_disc(self.pred_pos)))
        if ob_on:
            # 야생 2단계 3 의 2) 끝: 은신처 밀어내기·벽 자르기 뒤에도 원판(r + body_r) 안이면 이동 전 자리. 원판에 부딪혀 가려던 거리의 WALL_DEAD_FRAC 도
            # 못 갔으면 돌아선다(heading ← 가려던 이동의 반대 — 은신처 막다른 곳과 같은 꼴). C++ 꼴:
            #   if (InsideAnyObstacle(N)) N = Q;  if ((bObHit || bBack) && Want > Eps && |N − Q| < DeadFrac·Want) M = −SV / Want;
            back = obstacle_inside(self.pred_pos, self.obstacles, self._ob["body_r"])
            self.pred_pos[back] = old[back]
            want = np.sqrt((ob_step * ob_step).sum(1))
            dv = self.pred_pos - old
            dead = (ob_hit | back) & (want > EPS) & (np.sqrt((dv * dv).sum(1)) < WALL_DEAD_FRAC * want)
            if dead.any():
                move[dead] = -ob_step[dead] / want[dead][:, None]
            self._ob_wolf_hit += int(np.count_nonzero(ob_hit))
            self._ob_wolf_back += int(np.count_nonzero(back))
            self._ob_wolf_dead += int(np.count_nonzero(dead))
            self._ob_wolf_steps += M
            self.pred_ob_hit, self.pred_ob_back, self.pred_ob_dead = ob_hit, back, dead   # 스텝 뒤 훅(골든·시험 — C++ FThreatStepResult::bObstacle*)
        self.pred_head = normalize(move)
        self.pred_vel = self.pred_pos - old
        # 이번 이동이 전력 걸음이었나 — 추격형(근접·원거리)이 표적을 쫓음, 잠행형 돌진 상태(돌진 이동·마지막 판정 스텝), 플레이어 돌진 모드.
        # 상태는 이동 때 값(포획 뒤 갱신 `_threat_after` 전)이다. v3 현실성 (b) 의 스텝 뒤 훅 pred_running 과 야생 2단계 사냥 성공률 통계가 함께 쓴다
        if th is None:
            run = has_target.copy()
        else:
            run = has_target & (self.pred_type == PT_CHASER)
            run |= stalker & (self.stalk_state == ST_POUNCE)
            run |= self.pred_is_player & (self.player_mode == PM_CHARGE)
        if self._zh is not None:
            self.pred_running = run

        hit = (catch_d <= self.pred_catch_r[:, None]) & hunting[:, None]
        if self._pred_ranged_v1[:Mb].any():
            roll = self.rng.random((Mb, N)) < cfg.pred_ranged_catch_p
            if M > Mb:
                roll = np.vstack([roll, np.ones((M - Mb, N), dtype=bool)])
            hit &= np.where(self.pred_ranged[:, None], roll, True)
        if self.alive is not None:
            hit[:, ~self.alive] = False     # 통합 무대 (k): 시체는 잡히지 않는다(원거리 판정 난수 소비는 그대로)
        if safe_m is not None:          # v3 현실성 (c): 은신처 안 사슴은 잡히지 않는다(원거리 판정 난수 소비는 그대로)
            self._zs_saved_n += int(np.count_nonzero((hit & safe_m).any(0)))
            hit &= ~safe_m
        hit_d = np.where(hit, catch_d, np.inf)
        k = hit_d.argmin(1)
        got = np.isfinite(hit_d[ar, k])
        caught = np.zeros(N, dtype=bool)
        caught[k[got]] = True
        # 야생 2단계 통계 전용(동역학과 무관, 난수 없음): 늑대(플레이어형 위협 말고)의 사냥 시작·끝·성공·사냥 밖 포획을 유형별로 센다.
        # 잡음 = 이 늑대의 포획 판정이 참(같은 사슴을 둘이 잡으면 둘 다 — C++ 위협 Step 결과 Caught ≥ 0 과 같다)
        # 장면 도구(골든 내보내기·시험)가 위협 칸을 reset 뒤에 바꿔도 통계가 동역학을 막지 않게 모양을 맞춘다(유형 칸이 하나면 모두 그 유형)
        wolf = ~np.broadcast_to(self.pred_is_player, (M,)) if th is not None else np.ones(M, dtype=bool)
        if self._hunt_on.shape != (M,):
            self._hunt_on = np.zeros(M, dtype=bool)
        self._hunt_on, *hx = hunt_update(self._hunt_on, run & wolf, got & wolf)
        kind = np.broadcast_to(self.pred_type, (M,)) if th is not None else np.zeros(M, dtype=np.int8)
        for r_, x in enumerate(hx):
            self._hunt_n[r_] += np.bincount(kind[x], minlength=3)[:3]
        if self._wp is not None and got.any():
            # 야생 2단계 2 통계 전용: 늑대 포획 가운데 다른 앞장 늑대도 이번 스텝에 쫓던 사슴을 잡은 수(협동 포획)
            lt = self._pack_lead_tgt
            for m_ in np.flatnonzero(got & wolf):
                self._wp_catch_n += 1
                self._wp_pack_catch_n += int(bool(((lt == k[m_]) & (ar != m_)).any()))
        if self._al is not None:
            # v3 R2 M8 비명의 점: 잡은 위협(동시 포획이면 낮은 번호 = 위협 슬롯 순서, C++ 도 위협 슬롯 번호로 깬다). 헛경보 통계
            # 전용: 이번 스텝에 표적이 있었거나 돌진 중인 위협
            cb = np.full(N, -1, dtype=np.int64)
            for m in np.flatnonzero(got)[::-1]:
                cb[k[m]] = m
            self._caught_by = cb
            act = has_target & hunting
            if th is not None:
                act = act | (stalker & (self.stalk_state == ST_POUNCE)) | (
                    self.pred_is_player & (self.player_mode == PM_CHARGE))
            self._pred_active = act
        if self._zt is not None and th is not None:     # v3 R3 (h) 통계 전용: 잠행형 돌진의 포획(돌진 시작 때 표적의 땅)
            hp = stalker & (self.stalk_state == ST_POUNCE) & got
            if hp.any():
                self._zt_pounce_hit += np.bincount(self._zt_pounce_tc[hp], minlength=len(TERRAIN_NAMES))
        if zc is not None and got.any():                # v3 R3 (f) 5): 잡은 위협은 고정을 놓는다
            gl = got & (self.chase_tgt >= 0)
            self._zc_rel_catch += int(np.count_nonzero(gl))
            self._zc_catch_own += int(np.count_nonzero(gl & (self.chase_tgt == k)))
            self.chase_tgt[got] = -1
            self.chase_lost[got] = 0
        if self._rz or self._r3 or self._wf is not None:
            # 스텝 뒤 훅(통계·판정 전용 — 야생 (w3) 은 '이 사슴을 쫓음' 판정에 쓴다): 이번 스텝에 위협 m 이 쫓은 사슴 슬롯(없으면 −1). 추격 고정 세계에서는
            # 고정한 표적(시야 밖이면 마지막 자리로 가는 중인 그 표적)이다. 포획 뒤 놓기와 무관하게 이번 스텝의 값이다
            self.pred_target = np.where(has_target, j, -1).astype(np.int64)
        if th is None:
            self.pred_cd[got] = int(cfg.pred_eat_cd)
        else:
            self.pred_cd[got] = np.where(self.pred_is_player[got], th["player_cooldown"], int(cfg.pred_eat_cd))
            if sd is not None:
                self._stare_after(got, caught)
            self._threat_after(got, ts)
        if self._ws is not None and got.any():
            # 야생 (w2): 잡은 늑대(플레이어형 위협 말고)는 먹기가 끝난 뒤 배부름 sat 스텝을 쉰다
            gw = got & ~self.pred_is_player if th is not None else got
            self.pred_sat[gw] = self._ws_sat_steps
            self._ws_kills_n += int(np.count_nonzero(gw))
        if self._zn is not None:
            # v3 현실성 (d): 이번 스텝에 사냥 중이었나(표적 있음, 또는 스텝 끝 잠행형 돌진·대치) — 다음 `_daynight_update` 의 눕기 조건
            act = has_target.copy()
            if th is not None:
                act |= stalker & ((self.stalk_state == ST_POUNCE) | (self.stalk_state == ST_STANDOFF))
            self._zn_hunt = act
        return caught

    def _stare_check(self, dx, dy, dist, inv, perceived, hunting) -> None:
        """v3 R2 M7 C0 — 잠금 확인(M7a)과 노려보기 대치·들킴(M7b·M7c) (명세 2-1~2-3, 2-5 의 3·4). `_step_predators_v3` 가
        쿨다운·밤잠 초기화 바로 뒤, 표적 선택 전에 부른다. 모든 판정이 위협 이동 전에 끝나 위협을 처리하는 순서와 결과가 무관하다.

        잠행 = 잠행형의 배회·대치 상태 & 깨어 있음 & 쿨다운 0, 또는 플레이어의 잠행 모드 & 쿨다운 0 (`hunting` 은 쿨다운 0 &
        깨어 있음). 거리·위치는 C 시작 값(초식 이동 뒤, 포식자 이동 전)이고 heading 은 이번 스텝 FREEZE 제어기가 정한 값이다.
          3. 잠금이 있는데 잠행이 아니거나 추적 불가면 지운다(대치였으면 배회로, spot_cnt 0 — 깨진 대치로 센다). 추적 가능 =
             플레이어는 늘, 잠행형은 실거리 ≤ pred_view_r & 포식자 시야각 안. 둘 다 표적이 숨지 않았어야 한다(웅크린 HIDE·SLEEP).
          4. spot_r > 0 일 때만: S = 잠행 & 잠금 & 표적 FREEZE & 실거리 ≤ min(spot_r, 표적의 지금 탐지 반경) & 표적 heading 과
             (표적 → 위협) 의 cos ≥ spot_cos & 체감 거리 > 돌진 거리(잠행형 stalk_dist, 플레이어 player_charge_dist).
             잠행형: S 면 대치(처음이면 spot_cnt 1, 이어지면 + 1), spot_cnt 가 spot_steps 에 닿으면 물러남(stalk_left = balk_steps,
             방향 = 단위(포식자 − 표적) 한 번, 길이 0 이면 −heading, 잠금·spot_cnt 지움). 대치인데 S 가 아니면 배회(잠금은 남는다 —
             같은 스텝의 표적 선택·돌진 판정을 그대로 탄다). 플레이어: S 면 spot_cnt + 1, 아니면 0. spot_steps 에 닿으면
             spotted_left = spotted_steps, spot_cnt 0 (멈추지 않고 잠금도 그대로다). 추격형은 아무 영향이 없다.
        훅 stare_by 를 다시 정한다. C++ 꼴 (EcoStareDown.h — 위협 m 하나, ThreatStep 의 '잠금·노려보기' 자리):
          bool bCreep = (Type==Stalker && (State==Roam || State==Standoff) && bAwake && Cd==0)
                     || (Type==Player && Mode==Stalk && Cd==0);
          if (Lock.IsSet() && (!bCreep || !Trackable(m, Lock))) { Lock.Reset(); if (State==Standoff) { State=Roam; SpotCnt=0; } }
          bool bS = bCreep && Lock.IsSet() && Prey(Lock).Behavior==Freeze
                 && Dist(m, Lock) <= FMath::Min(SpotR, Prey(Lock).SeeR)
                 && (Prey(Lock).Facing | Dir(Prey(Lock).Pos, Q[m])) >= SpotCos
                 && Perceived(m, Lock) > (Type==Stalker ? StalkDist : PlayerChargeDist);
          if (Type==Stalker) {
            if (bS) { SpotCnt = (State==Standoff) ? SpotCnt+1 : 1; State = Standoff;
                      if (SpotCnt >= SpotSteps) { State=Balk; Left=BalkSteps; BalkDir=SafeDir(Q[m]-Prey(Lock).Pos, -H[m]);
                                                  Lock.Reset(); SpotCnt=0; } }
            else if (State==Standoff) { State=Roam; SpotCnt=0; }
          } else { SpotCnt = bS ? SpotCnt+1 : 0; if (SpotCnt >= SpotSteps) { SpottedLeft=SpottedSteps; SpotCnt=0; } }
        """
        sd, th, cfg, rs = self._sd, self._th, self.cfg, self._rs
        M, t = self.M, self.t
        ar = np.arange(M)
        st, lock, cnt = self.stalk_state, self.pred_lock, self.spot_cnt
        stalker = self.pred_type == PT_STALKER
        player = self.pred_is_player
        creep = hunting & ((stalker & ((st == ST_ROAM) | (st == ST_STANDOFF)))
                           | (player & (self.player_mode == PM_STALK)))
        self.stare_by = np.full(self.N, -1, dtype=np.int64)
        has = lock >= 0
        k = np.where(has, lock, 0)
        # 3. 잠금 확인
        hidden = self._rep_crouch[k] | (rs.behavior[k] == rep.SLEEP)
        if self._zs is not None and self._zs["untargetable"]:   # v3 현실성 (c): 은신처 안 표적은 추적할 수 없다(잠금을 지운다)
            hidden = hidden | self._zs_safe_m[ar, k]
        fov = (dx[ar, k] * self.pred_head[:, 0] + dy[ar, k] * self.pred_head[:, 1]) * inv[ar, k] >= cfg.pred_fov_cos
        track = (player | ((dist[ar, k] <= cfg.pred_view_r) & fov)) & ~hidden
        drop = has & ~(creep & track)
        if drop.any():
            lock[drop] = -1
            brk = drop & (st == ST_STANDOFF)
            st[brk] = ST_ROAM
            cnt[brk] = 0
            self._sd_break_n += int(np.count_nonzero(brk))
            self._sd_break_beh_n += int(np.count_nonzero(brk & (rs.behavior[k] != rep.FREEZE)))
            self._sd_break_t[k[brk]] = t
        if sd["spot_r"] <= 0.0:         # 중립: 노려보기 블록을 건너뛴다(비교하지 않는다)
            return
        # 4. 노려보기
        has = lock >= 0
        k = np.where(has, lock, 0)
        see_k = self._see_pred * self._rep_see[k]
        near = dist[ar, k] <= np.minimum(sd["spot_r"], see_k)
        eye = -(dx[ar, k] * self.head[k, 0] + dy[ar, k] * self.head[k, 1]) * inv[ar, k]
        far = perceived[ar, k] > np.where(player, th["player_charge_dist"], th["stalk_dist"])
        S = creep & has & (rs.behavior[k] == rep.FREEZE) & near & (eye >= sd["spot_cos"]) & far
        was = stalker & (st == ST_STANDOFF)
        s_st = stalker & S
        self._sd_standoff_n += int(np.count_nonzero(s_st & ~was))
        cnt[s_st] = np.where(was[s_st], cnt[s_st] + 1, 1)
        st[s_st] = ST_STANDOFF
        bk = s_st & (cnt >= sd["spot_steps"])
        if bk.any():
            st[bk] = ST_BALK
            self.stalk_left[bk] = sd["balk_steps"]
            v = self.pred_pos[bk] - self.pos[k[bk]]
            n = np.sqrt((v * v).sum(1))
            self.balk_dir[bk] = np.where((n > EPS)[:, None], v / np.maximum(n, EPS)[:, None], -self.pred_head[bk])
            lock[bk] = -1
            cnt[bk] = 0
            self._sd_balk_n += int(np.count_nonzero(bk))
        brk = was & ~S
        if brk.any():
            st[brk] = ST_ROAM
            cnt[brk] = 0
            self._sd_break_n += int(np.count_nonzero(brk))
            self._sd_break_beh_n += int(np.count_nonzero(brk & (rs.behavior[k] != rep.FREEZE)))
            self._sd_break_t[k[brk]] = t
        if player.any():
            cnt[player] = np.where(S[player], cnt[player] + 1, 0)
            sp = player & (cnt >= sd["spot_steps"])
            self._sd_spotted_n += int(np.count_nonzero(sp & (self.spotted_left == 0)))     # 새로 들킴(갱신은 세지 않는다)
            self.spotted_left[sp] = sd["spotted_steps"]
            cnt[sp] = 0
        for m in np.flatnonzero(S)[::-1]:           # 같은 개체를 여럿이 노려보면 낮은 번호 위협
            self.stare_by[k[m]] = m
        self._sd_stare_steps += int(np.count_nonzero(self.stare_by >= 0))

    def _stare_target(self, j, d_t, has_target, hunting, perceived):
        """v3 R2 M7a 표적 덮기 (명세 2-5 의 6): 사냥 중인 잠행 위협(잠행형 배회, 플레이어 잠행 모드)이 잠금을 갖고 있으면
        j = 잠금, d_t = 체감 거리(위협, 잠금) — 잠긴 표적이 얼어 체감 거리가 시야 반경을 넘어도 계속 쫓는다(옆 개체로 넘어가지
        않는다). 잠금이 없고 표적이 있으면 그 표적을 잠근다. target_lock false 면 표적 선택은 그대로 두고 잠금 = 이번 표적
        (없으면 −1) 기록만 한다. 돌진 시작 조건은 그대로다(잠긴 d_t ≤ 돌진 거리).
        새 잠금은 추적 가능을 보지 않는다(명세 2-1 '표적을 고르면 잠근다' 글자 그대로, 구현 검토 10-12 에 이렇게 고정했다). 이번
        스텝 표적 선택이 숨은 개체(웅크린 HIDE·SLEEP — 주로 맵 전체를 보는 플레이어)를 골랐으면 그 개체를 잠그고, 다음 스텝 C0 이
        숨음을 보고 지운다. 그래서 스텝 끝 훅 pred_lock(언리얼 LockedPrey)은 '이번 스텝에 쫓은 잠금 표적'이고 숨은 개체를 가리킬
        수 있으며, 그 개체가 다음 스텝에 숨기를 풀면 잠금이 이어진다. lock_n 은 새 잠금 수라 같은 숨은 개체를 다시 잠그면 다시 센다.
        C++ 꼴 (EcoStareDown.h, ThreatStep 의 표적 선택 뒤 — 2-5 의 6):
          bool bCreepHunt = bHunting && ((Type==Stalker && State==Roam) || (Type==Player && Mode==Stalk));
          if (bCreepHunt && bTargetLock) {
            if (Lock.IsSet()) { J = Lock; DT = Perceived(m, Lock); bHasTarget = true; }
            else if (bHasTarget) Lock = J; }            // 새 잠금은 Trackable 을 보지 않는다(숨은 개체면 다음 C0 이 지운다)
          else if (bCreepHunt) Lock = bHasTarget ? J : None;   // target_lock false: '지난 스텝 표적' 기록만"""
        lock, M = self.pred_lock, self.M
        ar = np.arange(M)
        stalker = self.pred_type == PT_STALKER
        creep_h = hunting & ((stalker & (self.stalk_state == ST_ROAM))
                             | (self.pred_is_player & (self.player_mode == PM_STALK)))
        if self._sd["target_lock"]:
            lk = creep_h & (lock >= 0)
            if lk.any():
                j = np.where(lk, lock, j)
                d_t = np.where(lk, perceived[ar, j], d_t)
                has_target = has_target | lk
            new = creep_h & (lock < 0) & has_target
            lock[new] = j[new]
        else:
            rec = np.where(has_target, j, -1)
            new = creep_h & (rec >= 0) & (rec != lock)
            lock[creep_h] = rec[creep_h]
        self._sd_lock_n += int(np.count_nonzero(new))
        return j, d_t, has_target

    def _stare_after(self, got: np.ndarray, caught: np.ndarray) -> None:
        """v3 R2 M7 포획 뒤 (명세 2-5 의 11): 잡은 위협의 잠금을 지운다. 통계: 들킨 돌진 포획, '먼저 눈을 돌렸다' 포획(깨진 대치
        뒤 BLINK_STEPS 안에 그 표적이 잡힘), 잠금 위협-스텝."""
        self.pred_lock[got] = -1
        self._sd_spotted_charge_catch_n += int(np.count_nonzero(got & self.spotted_charge))
        self._sd_charge_catch_n += int(np.count_nonzero(got & self.pred_is_player & (self.player_mode == PM_CHARGE)
                                                        & ~self.spotted_charge))
        c = np.flatnonzero(caught)
        if len(c):
            blink = c[self.t - self._sd_break_t[c] <= BLINK_STEPS]
            self._sd_blink_n += len(blink)
            self._sd_break_t[blink] = -(10 ** 9)
        self._sd_lock_steps += int(np.count_nonzero(self.pred_lock >= 0))

    def _threat_motion(self, move, speed, wander, has_target, d_t, exh0, rest0):
        """잠행형·플레이어의 이번 스텝 이동 방향·속력과 상태 시작(돌진·플레이어 돌진). `_step_predators_v3` docstring.
        v3 R2 M7(stare_down): 돌진 시작이 잠금을 지운다. 플레이어 돌진을 시작할 때 들킴(spotted_left > 0)이면 그 돌진 전체가
        들킨 돌진(속력 min(player_speeds[2], spotted_charge_speed) × herb_speed)이다. 대치는 속력 0·표적 쪽, 물러남은
        balk_speed × herb_speed 로 balk_dir 쪽."""
        th, hs, sd = self._th, self.cfg.herb_speed, self._sd
        stalker = self.pred_type == PT_STALKER
        st, left = self.stalk_state, self.stalk_left
        roam = stalker & (st == ST_ROAM)
        start = roam & has_target & (d_t <= th["stalk_dist"])
        st[start] = ST_POUNCE
        left[start] = th["pounce_steps"]
        self._th_pounce[0] += int(np.count_nonzero(start))
        if sd is not None:
            self.pred_lock[start] = -1
        stalking = roam & has_target & ~start
        pounce = stalker & (st == ST_POUNCE)
        final = pounce & (left <= 0)
        dash = pounce & ~final
        speed = np.where(stalking, th["stalk_speed"] * hs, speed)
        speed = np.where(dash, th["pounce_speed"] * hs, speed)
        speed = np.where(exh0 | final, th["exhaust_speed"] * hs, speed)
        move = np.where(((dash & ~has_target) | final)[:, None], self.pred_head, move)
        ps = th["player_speeds"]
        for i in np.flatnonzero(self.pred_is_player):
            if self.player_mode[i] == PM_STALK and has_target[i] and d_t[i] <= th["player_charge_dist"]:
                self.player_mode[i] = PM_CHARGE
                self.player_left[i] = th["player_charge_steps"]
                self._th_charge += 1
                if sd is not None:                      # v3 R2: 돌진 시작은 잠금을 지우고, 들킴 중이면 들킨 돌진이다
                    self.pred_lock[i] = -1
                    self.spotted_charge[i] = bool(self.spotted_left[i] > 0)
                    self._sd_spotted_charge_n += int(self.spotted_charge[i])
            mode = self.player_mode[i]
            if mode == PM_WANDER:
                speed[i], move[i] = ps[0] * hs, wander[i]
            elif mode == PM_STALK:
                speed[i] = ps[1] * hs                   # 표적 쪽(없으면 배회)
            elif mode == PM_CHARGE and self.player_left[i] > 0:
                speed[i] = ps[2] * hs
                if sd is not None and self.spotted_charge[i]:     # 들킨 돌진의 속력 상한(초식 뛰기보다 느리다)
                    speed[i] = min(ps[2], sd["spotted_charge_speed"]) * hs
                if not has_target[i]:
                    move[i] = self.pred_head[i]
            else:                                       # 휴식, 또는 돌진 뒤 마지막 판정 스텝
                speed[i], move[i] = 0.0, self.pred_head[i]
        if sd is not None:
            so = np.flatnonzero(stalker & (st == ST_STANDOFF))
            if len(so):                                 # 대치: 멈춰서 잠긴 표적 쪽을 본다
                v = self.pos[np.maximum(self.pred_lock[so], 0)] - self.pred_pos[so]
                n = np.sqrt((v * v).sum(1))
                ok = (n > EPS) & (self.pred_lock[so] >= 0)
                move[so] = np.where(ok[:, None], v / np.maximum(n, EPS)[:, None], self.pred_head[so])
                speed[so] = 0.0
            bk = stalker & (st == ST_BALK)              # 물러남: balk_dir 쪽으로 걸어 나간다(사냥 안 함)
            speed[bk] = sd["balk_speed"] * hs
            move[bk] = self.balk_dir[bk]
        return move, speed, dict(final=final, dash=dash, exh0=exh0, rest0=rest0)

    def _threat_after(self, got: np.ndarray, ts: dict) -> None:
        """포획 뒤 잠행형·플레이어 상태 갱신과 유형별 포획 수 (`_step_predators_v3` docstring)."""
        th = self._th
        stalker = self.pred_type == PT_STALKER
        st, left = self.stalk_state, self.stalk_left
        hitp = stalker & (st == ST_POUNCE) & got
        self._th_pounce[1] += int(np.count_nonzero(hitp))
        st[hitp] = ST_ROAM
        left[hitp] = 0
        fin = ts["final"] & ~got
        st[fin] = ST_EXHAUST if th["exhaust_steps"] > 0 else ST_ROAM
        left[fin] = th["exhaust_steps"]
        cont = ts["dash"] & ~got
        left[cont] -= 1
        e = ts["exh0"]
        left[e] -= 1
        back = e & (left <= 0)
        st[back] = ST_ROAM
        left[back] = 0
        sd = self._sd
        if sd is not None:              # v3 R2: 물러남 남은 스텝 감소 → 0 이면 배회, 들킴 남은 스텝 감소
            bk = stalker & (st == ST_BALK)
            left[bk] -= 1
            done = bk & (left <= 0)
            st[done] = ST_ROAM
            left[done] = 0
            self.spotted_left = np.maximum(self.spotted_left - 1, 0)
        kind = np.where(self.pred_is_player, 3, np.where(stalker, 2, np.where(self.pred_ranged, 1, 0)))
        self._th_catch += np.bincount(kind[got], minlength=4)
        for i in np.flatnonzero(self.pred_is_player):
            mode = self.player_mode[i]
            if mode == PM_CHARGE:
                if got[i] or self.player_left[i] <= 0:
                    self.player_mode[i] = PM_REST
                    self.player_left[i] = th["player_rest_steps"]
                    if sd is not None:          # 돌진이 끝나면 들킨 돌진 표시를 지운다
                        self.spotted_charge[i] = False
                    if th["player_rest_steps"] <= 0:
                        self._player_new_mode(i)
                else:
                    self.player_left[i] -= 1
            else:                                       # 배회·잠행·휴식: 남은 길이를 줄이고 끝나면 새 모드
                self.player_left[i] -= 1
                if self.player_left[i] <= 0:
                    self._player_new_mode(i)

    def _eat(self, e_drained: np.ndarray, mult: np.ndarray | None = None) -> np.ndarray:
        """셀당 총 수요를 잔량에 비례 배분한다. 개체별 루프 없음 (§1.1).

        수요는 **흡수 가능량**으로 제한한다: 배부른 개체가 먹이를 계속 퍼가면 맵 전체가
        벗겨져서(측정: food가 0.02로 수렴) 먹이 탐색이 무의미해진다. 이렇게 두면 총
        소비량이 총 대사 수요를 따라가고 패치가 유지된다.

        `mult` (N,) 는 v2.1 보행 섭식 배수다(speed). 흡수 가능량 상한까지 자른 want 에 곱한 뒤 셀 수요를 합친다.
        뛰는 개체(0)는 수요가 없어 같은 셀 개체의 몫을 줄이지 않는다. None 이면 v1 과 같다.
        """
        cfg = self.cfg
        want = np.clip(
            (cfg.max_energy - e_drained) / cfg.food_energy_per_unit, 0.0, cfg.food_eat_rate
        )
        if mult is not None:
            want = want * mult
        ix, iy = self._cell_index(self.pos)
        flat = iy * self.gw + ix
        cells = self.gw * self.gw
        demand = np.bincount(flat, weights=want, minlength=cells)
        taken = np.minimum(demand, self.food.reshape(-1))
        frac = np.divide(taken, demand, out=np.zeros(cells), where=demand > 0)
        self.food -= taken.reshape(self.gw, self.gw)
        if self._fv is not None:
            self._fv_taken = taken          # v2.0b 훼손이 셀별 섭취량을 쓴다 (_food_v_step)
        return want * frac[flat]

    def _food_v_step(self) -> None:
        """v2.0b 먹이 2층의 한 스텝 (계획서 4.9.1). `step` 7) 에서 v1 재생 대신 부른다.

        셀마다 F = self.food, V = self.food_v(식생 용량), cap0 = self.food_cap, r = self.regen_field
        (은신처 0.3배 포함, v1 그대로). 한 스텝의 순서 — C++ 로 옮길 때 이 순서를 지킨다:

          3)  섭식 (`_eat`): F ← F − taken. taken ≤ F 라 F ≥ 0.
              4)~6) 번식·사망·피식 EMA 는 F·V 를 읽지 않으므로 훼손을 3) 직후에 해도 결과가 같다.
          7a) 훼손 (taken > 0 인 셀만): V ← V − α·taken·(1 − F/V). F 는 섭취 직후 값, V 는 훼손 전 값.
              taken > 0 이면 섭취 전 F ≥ taken > 0 이고 V ≥ 섭취 전 F 라 V > 0 이다 — 0 나눗셈이 없다.
          7b) 하한: V ← max(V, floor·cap0).
          7c) F ← min(F, V). α ≤ 1 이면 수학적으로는 바뀌지 않지만 반올림·α > 1 대비로 둔다.
          7d) 재생 (모든 셀): F ← F + r·(V − F), F ← min(F, V). v1 식(목표·상한 cap0)의 cap0 를 V 로
              바꾼 것이다. v1 은 clip(F, 0, cap0) 이지만 여기서는 F ≥ 0, V ≥ F 라 r·(V − F) ≥ 0 이고
              하한 0 이 저절로 지켜져 상한만 자른다(결과가 같다).
          7e) 휴식 회복 (모든 셀): V ← V + ρ·(cap0 − V), ρ = 1 − 2^(−1/h). 섭식이 없으면 cap0 − V 가
              h 스텝마다 절반이 된다. V 가 cap0 쪽으로만 움직이므로 F ≤ V ≤ cap0, V ≥ floor·cap0 가 유지된다.

        taken 은 고정 스텝 하나(1스텝 = 0.133s) 동안 그 셀에 들어간 모든 개체 섭취의 합이고(`_eat` 의 셀별 합),
        7a~7e 는 모든 섭식이 끝난 뒤 셀마다 한 번 계산한다. (1 − F/V) 가 비선형이라 개체마다·프레임마다 V 를
        바로 깎으면 같은 섭취량에서도 훼손이 작아진다(막 자란 셀을 8번에 나눠 먹으면 약 −45%). C++ 는
        ConsumeFood 를 셀별 버퍼에 누적했다가 같은 고정 간격으로 한 번 갱신한다. r·ρ 는 스텝당 값이라 간격 dt 를
        바꾸면 r' = 1 − (1 − r)^(dt/0.133s), ρ' = 1 − 2^(−dt/(h·0.133s)) 로 다시 환산하고, α 는 분할에 불변이
        아니므로 다시 보정한다.

        스텝 끝 불변식: 0 ≤ F ≤ V ≤ cap0, floor·cap0 ≤ V. cap0 = 0 셀은 F = V = 0 이다.
        taken > 0 가드는 최적화이면서 필수다. taken = 0 이고 V > 0 인 셀에서 7a~7c 는 항등이지만, cap0 = 0 셀
        (V = F = 0)을 조밀하게 계산하면 0·(1 − 0/0) = NaN 이 되어 F 와 관측 0 의 food_blur 누적합으로 퍼진다.
        그래서 먹힌 셀(많아야 N 개)만 계산한다(C++ 도 `if (Taken > 0)`). 가드를 단 조밀 계산과 비트 단위로 같다.
        α = 0 이고 V = cap0 로 시작하면 V 가 비트 단위로 cap0 에 머물러 v2.0(= v1) 세계와 같다
        (둘 다 tests/test_food_v2.py).
        """
        fv = self._fv
        F, V = self.food.reshape(-1), self.food_v.reshape(-1)     # 연속 배열의 뷰 — 제자리 갱신
        taken = self._fv_taken
        k = (taken > 0.0).nonzero()[0]      # taken ≥ 0. float 배열의 flatnonzero 보다 몇 배 빠르다
        if k.size:
            tk, f, v = taken[k], F[k], V[k]
            v = np.maximum(v - fv["alpha"] * tk * (1.0 - f / v), self._fv_floor.reshape(-1)[k])
            V[k] = v
            F[k] = np.minimum(f, v)
            self._fv_eaten.reshape(-1)[k] += tk
            self._fv_last_eat.reshape(-1)[k] = self.t + 1     # 이 스텝이 끝난 뒤의 self.t
        # 7d·7e 는 임시 배열 하나를 같이 쓴다 (r·(V − F) 와 (V − F)·r 은 같은 값이다)
        d = np.subtract(self.food_v, self.food)
        d *= self.regen_field
        self.food += d
        np.minimum(self.food, self.food_v, out=self.food)
        np.subtract(self.food_cap, self.food_v, out=d)
        d *= self.food_v_rho
        self.food_v += d

    def _respawn(self, dead: np.ndarray) -> None:
        """§4.3 — 죽은 슬롯에 랜덤 위치로 리스폰. 개체군 동역학은 넣지 않는다."""
        # v1 스트림에서 위치 (k, 2)·각 k 개를 이 순서로 뽑고, 슬롯을 새 개체로 만드는 나머지는 `_spawn_slots` 가 한다(통합 무대 10-15 에 떼어
        # 냈다 — 줄 순서는 그대로라 같은 세계다)
        r, k = self.rng, len(dead)
        pos = r.uniform(0.0, self.size, (k, 2))
        ang = r.uniform(0.0, 2 * np.pi, k)
        self._spawn_slots(dead, pos, np.stack([np.cos(ang), np.sin(ang)], 1))
        if self._ob is not None and len(self.obstacles):
            # 야생 2단계 3 의 5): 원판 안에 난 새 개체를 밖으로(v1 난수 호출은 위에서 그대로 했다)
            self.pos[dead], mv, fl = obstacle_push_out(self.pos[dead], self.obstacles, self._ob["body_r"], self.size)
            self._ob_push_moved += mv
            self._ob_push_failed += fl

    def _spawn_slots(self, dead: np.ndarray, pos: np.ndarray, head: np.ndarray) -> None:
        """슬롯 `dead` 를 위치 `pos` (k, 2)·방향 `head` (k, 2)의 새 개체로 만든다: 에너지 init_energy, 번식 쿨다운 0, 켠 기능의 개체 상태 초기화
        (리스폰과 같은 새 개체 — 행동 상태는 GRAZE 진입·세대 + 1, 잠금·추격 고정 놓기). 난수는 켠 기능이 원래 리스폰 때 뽑던 것만 뽑는다
        (daynight.start_induce 의 part 3). 통합 무대 (k) 부활 없음 세계면 그 슬롯을 다시 산 슬롯으로 둔다.
        번식으로 태어나는 다음 단계(아직 없음)는 빈 슬롯(~alive)을 골라 부모 곁 자리로 이것을 부른다 — 위치·방향을 정하는 난수는 그 기능의
        자기 스트림에서 뽑는다(v1 스트림을 쓰지 않는다, features.py 규칙 1). 부른 뒤 그 행만 다시 관측한다(`_observe_subset`)."""
        k = len(dead)
        self.pos[dead] = pos
        self.head[dead] = head
        self.energy[dead] = self.cfg.init_energy
        self.repro_cd[dead] = 0
        if self._vg is not None:        # v2.2 개체별 상태 초기화 (계획서 4.2·4.4). 난수를 쓰지 않는다
            self.threat[dead] = 0.0
            self.threat_dir[dead] = 0.0
            self._wide[dead] = False
            self._near[dead] = False            # 통계 전용 기준 상태도 새 개체로 (`_perceive`)
            self._tr_truth[dead] = 0.0
        if self._dn is not None and self._dn["start_induce"] > 0.0:
            # v2.4 시작 상태 유도(탐침 대응, 0 이면 없음): daynight 스트림 part 3 에서 리스폰 개체마다 2개(u, 에너지)를
            # 늘 뽑고(소비가 결과와 무관하다) u < start_induce 면 에너지를 U[0.2, 0.5]·max_energy 로 둔다. 낮 고정 세계는
            # reset 유도처럼 바꾸지 않는다(낮 고정 세계 = v2.1 동역학). v1 스트림 호출(위)은 그대로다
            g = self.feature_rng("daynight", 3)
            u = g.random(k)
            e = g.uniform(INDUCE_ENERGY[0], INDUCE_ENERGY[1], k) * self.cfg.max_energy
            if not self.day_fixed:
                self.energy[dead] = np.where(u < self._dn["start_induce"], e, self.energy[dead])
        if self._rp is not None:
            # v3: 새 개체는 GRAZE 진입 상태(잠금 lock_graze), 사건 기준값은 리스폰 때 값(에너지·어둠), 세대 + 1 로 사건 결정
            # 지연을 새로 받는다(C++ AgentKey 가 리스폰마다 새 값인 것과 같다). 난수를 쓰지 않는다.
            # 스텝 뒤 훅(behavior 등)은 바꾸지 않는다(`_rep_export`). 깜빡임 통계는 이전 개체와 잇지 않는다
            self._rep_gen[dead] += 1
            self._rs.reset_slots(dead, self._rp, self.energy[dead] / self.cfg.max_energy, self.dark, self.seed,
                                 self._rep_gen[dead])
            self._rep_see[dead] = self._rp["graze_head_down"]
            self._rep_see_last[dead] = self._rp["graze_head_down"]
            self._rep_before[dead] = -1
            self._rep_last_sw[dead] = -(10 ** 9)
        if self._sd is not None:
            # v3 R2 M7: 리스폰한 슬롯을 잠근 위협은 잠금을 지우고 대치였으면 배회로 되돌린다(새 개체다). spot_cnt 도 0
            hit = np.isin(self.pred_lock, dead)
            if hit.any():
                self.pred_lock[hit] = -1
                self.stalk_state[hit & (self.stalk_state == ST_STANDOFF)] = ST_ROAM
                self.spot_cnt[hit] = 0
            self._sd_break_t[dead] = -(10 ** 9)
        if self._zc is not None:
            # v3 R3 (f): 표적이 죽으면(리스폰한 슬롯은 새 개체다) 고정을 놓는다. 잡은 위협은 포획 때 이미 놓았다
            hit = np.isin(self.chase_tgt, dead)
            if hit.any():
                self.chase_tgt[hit] = -1
                self.chase_lost[hit] = 0
                self._zc_rel_dead += int(np.count_nonzero(hit))
        if self._al is not None:
            # v3 R2 M8: 경보 상태는 RepState.reset_slots 가 0 으로 둔다. 통계 전용 개체 상태도 새 개체로
            self._al_src[dead] = -1
            self._al_wave_last[dead] = -1
            self._al_onset_t[dead] = -1
            self._al_e7_t[dead] = -(10 ** 9)
        if self._wr is not None:
            self.reserve[dead] = self._wr["init"]      # 야생 (w1): 새 개체는 시작 비축으로
        if self._wf is not None:
            self.wf_mode[dead] = WF_NONE               # 야생 (w3): 새 개체는 덮기 없이 시작한다
            self.wf_dir[dead] = 0.0
        if self.alive is not None:
            # 통합 무대 (k): 빈 슬롯을 다시 채우면 산 슬롯이다(새 배열 — 스텝 안의 L 을 바꾸지 않는다)
            self.alive = self.alive.copy()
            self.alive[dead] = True
            self.death_t[dead] = -1
            self.death_cause[dead] = 0

    def _ist_bury(self, dead: np.ndarray, caught: np.ndarray) -> None:
        """통합 무대 (k) 부활 없음: 이번 스텝에 죽은 슬롯 `dead` 를 시체로 둔다(`step` 의 관측 뒤, 리스폰 자리). 위치·방향·에너지·행동 상태는
        죽은 때 값 그대로이고 다음 스텝부터 관측(동족)·표적·포획·먹이·이동·번식·밤잠 근처 판정에서 빠진다(모듈 docstring (k)). 난수를 쓰지 않는다.
        훅: alive ← 새 배열(L & ¬dead), death_t ← 지금 t(이 스텝이 끝난 뒤의 t), death_cause ← 1 잡힘·2 굶음.
        추격 고정(realism_chase)은 표적이 죽으면 리스폰 때처럼 놓는다(chase_rel_dead_n 에 센다).
        번식 출생(다음 단계, 아직 없음): 번식 사건(`step` 4) 의 repro)마다 빈 슬롯(~alive) 하나를 골라 `_spawn_slots(슬롯, 부모 곁 자리, 방향)` 을
        부르고 그 행을 다시 관측한다. 슬롯이 모자라면(용량 N) 태어나지 않는다. 피식 EMA 분모는 ema_den 으로 고정한다. 학습에 쓰려면 vec_env 가
        빈 슬롯의 행을 PPO 손실에서 빼는 마스크가 있어야 한다(지금은 vec_env 가 이 세계를 받지 않는다)."""
        self.alive = self.alive.copy()
        self.alive[dead] = False
        self.death_t[dead] = self.t
        self.death_cause[dead] = np.where(caught[dead], 1, 2).astype(np.int8)
        if self._zc is not None:
            hit = np.isin(self.chase_tgt, dead)
            if hit.any():
                self.chase_tgt[hit] = -1
                self.chase_lost[hit] = 0
                self._zc_rel_dead += int(np.count_nonzero(hit))

    # ------------------------------------------------------------------ #
    # 야생 1단계 (모듈 docstring '야생 1단계', 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md)
    # ------------------------------------------------------------------ #

    def _wild_reset(self) -> None:
        """야생 1단계 상태·통계 칸 (reset, 하루 길이·위협 수가 정해진 뒤). 난수를 쓰지 않는다. 일 단위 계수를 이 세계의 dn_period 로 옮긴다."""
        N, M = self.N, self.M
        if self._wr is not None:
            self.reserve = np.full(N, self._wr["init"])
            # 비축 용량(E 단위) = 걷기 대사(× energy_drain)만으로 reserve_days 일을 버티는 에너지
            self._wr_cap = self._wr["reserve_days"] * self.dn_period * self.cfg.energy_drain
            self.weak = np.zeros(N, dtype=bool)
            self._wr_used = 0.0             # 비축에서 꺼내 쓴 에너지 합(E 단위)
            self._wr_refill = 0.0           # 비축으로 옮긴 에너지 합
            self._wr_live_n = 0             # 산 개체-스텝
            self._wr_weak_n = 0             # 그중 약한 개체-스텝(스텝 첫머리 E < weak_e)
            self._wr_weak_caught = 0        # 약한 채로 잡힌 수
        if self._ws is not None:
            self.pred_sat = np.zeros(M, dtype=np.int64)    # 남은 배부름 스텝(먹기가 끝난 뒤부터 준다)
            self.pred_sated = np.zeros(M, dtype=bool)      # 스텝 뒤 훅: 이번 스텝에 배불러 쉬었나
            self._ws_sat_steps = wild_days_to_steps(self._ws["sat_days"], self.dn_period)
            self._ws_sated_n = self._ws_eat_n = self._ws_steps_n = self._ws_kills_n = 0
        if self._wf is not None:
            self.wf_mode = np.zeros(N, dtype=np.int8)      # 다음 스텝의 덮기(WF_*)
            self.wf_dir = np.zeros((N, 2))                 # 경계·도주 방향(단위, 없으면 0)
            self._wf_mode_n = np.zeros(len(WF_MODE_NAMES), dtype=np.int64)   # 실행한 덮기별 산 개체-스텝
            self._wf_panic_starts = self._wf_panic_ends = self._wf_panic_end_shelter = 0
        if self._wp is not None:
            # 야생 2단계 2 스텝 뒤 훅: 이번 스텝에 도운·기다린·은신처 문으로 간 늑대, 고른 사슴(없으면 −1). 통계 칸
            self.pack_help = np.zeros(M, dtype=bool)
            self.pack_wait = np.zeros(M, dtype=bool)
            self.pack_door = np.zeros(M, dtype=bool)
            self.pack_prey = np.full(M, -1, dtype=np.int64)
            self._pack_lead_tgt = np.full(M, -1, dtype=np.int64)    # 이번 스텝 앞장 늑대의 표적(앞장이 아니면 −1) — 협동 포획 셈
            self._pack_p0 = self.pos.copy()                          # 이번 스텝 사슴 이동 전 위치(`step` 이 이동 직전에 다시 쓴다)
            self._wp_steps_n = self._wp_lead_n = self._wp_help_n = self._wp_wait_n = self._wp_door_n = 0
            self._wp_catch_n = self._wp_pack_catch_n = 0

    def _wild_reserve_step(self, e_new: np.ndarray, gain_e: np.ndarray, live: np.ndarray | None) -> np.ndarray:
        """야생 (w1) `step` 3): 대사·섭식 뒤 E(e_new, max_energy 로 자른 값)에 비축을 적용한 E 를 돌려주고 self.reserve 를 바꾼다(산 개체만).
        gain_e = 이번 스텝 먹은 에너지(먹이 × food_energy_per_unit). 모자람을 다 채우면 E = 0, R 이 모자라면 R = 0 이고 E 는 남은 모자람(< 0)."""
        wr, cap = self._wr, self._wr_cap
        act = np.ones(self.N, dtype=bool) if live is None else live
        R = self.reserve.copy()
        e_out = e_new.copy()
        need = act & (e_new < 0.0)
        if need.any():
            want = -e_new[need] / cap
            r0 = R[need]
            covered = want <= r0
            e_out[need] = np.where(covered, 0.0, e_new[need] + r0 * cap)
            R[need] = np.where(covered, r0 - want, 0.0)
            self._wr_used += float((np.minimum(want, r0) * cap).sum())
        if wr["refill_frac"] > 0.0:
            fill = act & (e_out >= wr["refill_e"]) & (R < 1.0) & (gain_e > 0.0)
            if fill.any():
                mv = np.minimum(wr["refill_frac"] * gain_e[fill], (1.0 - R[fill]) * cap)
                e_out[fill] -= mv
                R[fill] = np.minimum(R[fill] + mv / cap, 1.0)
                self._wr_refill += float(mv.sum())
        self.reserve = R
        self._wr_live_n += int(np.count_nonzero(act))
        self._wr_weak_n += int(np.count_nonzero(self.weak & act))
        return e_out

    def _wf_hunting(self) -> np.ndarray:
        """야생 (w3) 사냥 중인 위협 (M,): 깨어 있고 먹는 중(쿨다운 > 0)이 아니고 배부르지(pred_sat > 0) 않다. 플레이어형 위협은 휴식 모드면 아니다."""
        h = self.pred_cd == 0
        if self._ps is not None:
            h = h & ~self.pred_asleep
        if self._ws is not None:
            h = h & (self.pred_sat == 0)
        if self._th is not None and self.M > self.M_base:
            h = h & ~(self.pred_is_player & (self.player_mode == PM_REST))
        return h

    def _wf_commit(self, res: dict, dobs: dict) -> None:
        """야생 (w3) A — C++ CommitKeepAway 와 같은 꼴: 덮기(도주 FLEE·웅크림 HIDE)가 걸린 산 개체가 arbitrate 뒤에도 그 행동이 아니면(잠금 중·
        기상 중·HIDE 도착 전) 곧바로 들어간다(진입 잠금·seq·놀람 정지 그대로, HIDE 는 은신처 안이라 곧바로 도착). 미뤄 둔 사건 결정은 버린다."""
        rs, rp = self._rs, self._rp
        live = np.ones(self.N, dtype=bool) if self.alive is None else self.alive
        pan = (self.wf_mode == WF_PANIC) & live
        shl = (self.wf_mode == WF_SHELTER) & live
        over = pan | shl
        if not over.any():
            return
        target = np.where(pan, rep.FLEE, rep.HIDE).astype(np.int64)
        need = over & ((rs.behavior != target) | rs.waking | (shl & ~rs.arrived))
        if need.any():
            rep._enter(rs, rp, need, target, dobs["in_cover"], dobs["cover_k"])
            res["switch"] = res["switch"] | need
        rs.ev_wait = np.where(over, -1, rs.ev_wait)
        rs.phase = rep.phase_of(rs, rp)

    def _wf_alert_control(self, out: dict, inp: dict) -> None:
        """야생 (w3) B 경계: 두뇌 행동이 GRAZE 인 경계 개체는 걸으며 먹고(보행·섭식·대사 = 걷기) GRAZE 조향 + alert_w·덮기 방향으로 멀어진다.
        고개를 든다(자기 탐지 반경 배수 1). 다른 행동(두뇌의 FLEE·HIDE·SLEEP)은 그대로다."""
        rs, rp, sp, cfg = self._rs, self._rp, self._sp, self.cfg
        al = (self.wf_mode == WF_ALERT) & (rs.behavior == rep.GRAZE) & (self.wf_dir != 0.0).any(1)
        if self.alive is not None:
            al &= self.alive
        if not al.any():
            return
        d = (rp["graze_forage"] * inp["food_grad"][al] + rp["graze_cohesion"] * inp["to_centroid"][al]
             + cfg.sep_weight * inp["separation"][al] + self._wf["alert_w"] * self.wf_dir[al])
        n = normalize(d)
        n = np.where(((n * n).sum(1) > EPS * EPS)[:, None], n, self.wf_dir[al])
        out["vel"][al] = n * (cfg.herb_speed * sp["speed"][GAIT_WALK])
        out["gait"][al] = GAIT_WALK
        out["eat"][al] = sp["eat"][GAIT_WALK]
        out["drain"][al] = sp["drain_mult"][GAIT_WALK]
        out["see"][al] = 1.0

    def _wf_update(self, done: np.ndarray) -> None:
        """야생 (w3) H: 스텝 끝 기하 self._g(관측과 같은 위치·보임, 리스폰 관측 포함)로 다음 스텝의 덮기 wf_mode·wf_dir 를 정한다(모듈 docstring
        '야생 1단계' (w3) 순서). 이번 스텝에 실행한 덮기를 센다. 덮기(도주·웅크림)가 풀리면 잠금 0·미뤄 둔 사건 지움(두뇌가 곧바로 고른다)."""
        wf, rs, g = self._wf, self._rs, self._g
        N, M = self.N, self.M
        live = np.ones(N, dtype=bool) if self.alive is None else self.alive
        prev = self.wf_mode
        self._wf_mode_n += np.bincount(prev[live | done], minlength=len(WF_MODE_NAMES))
        nxt = np.zeros(N, dtype=np.int8)
        dirs = np.zeros((N, 2))
        in_cov = g["in_cover"]
        if M > 0:
            hunt = self._wf_hunting()[None, :]
            pv = g["wf_pvis"]                                   # 알아챔(시야·청각, 자는 위협은 이미 빠졌다)
            ex = self.pred_pos[:, 0][None, :] - self.pos[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - self.pos[:, 1:2]
            pd = np.sqrt(ex * ex + ey * ey)
            pinv = 1.0 / np.maximum(pd, EPS)
            c = -(self.pred_vel[:, 0][None, :] * ex + self.pred_vel[:, 1][None, :] * ey) * pinv / self.cfg.herb_speed
            appr = (np.clip(c, -1.0, 1.0) + 1.0) * 0.5 >= wf["approach"]     # 관측 pred_approach 와 같은 식
            tgt = getattr(self, "pred_target", None)
            locked = (tgt[None, :] == np.arange(N)[:, None]) if tgt is not None else np.zeros((N, M), dtype=bool)
            coming = hunt & (locked | appr)
            nh = pv & hunt & (pd <= wf["alert_r"])               # 경계 거리 안에서 알아챈 사냥 중인 늑대
            nr = (pv & ~hunt & (pd <= wf["alert_r"])) if wf["rest_alert"] else np.zeros((N, M), dtype=bool)
            near_h = hunt & (pd <= wf["safe_r"])                  # 안전 거리 안의 사냥 중인 늑대(실거리 — 쫓는 늑대는 돌아보며 안다)
            if wf["hold_awake"]:
                # 10-16: 지난 도주는 깨어 있는 늑대(사냥·먹기·배부름, 자는 늑대 말고)가 안전 거리 안에 하나라도 있으면 이어진다
                awake = ~self.pred_asleep if self._ps is not None else np.ones(M, dtype=bool)
                near_h = awake[None, :] & (pd <= wf["safe_r"])
            panic_now = (nh & ((pd <= wf["flight_r"]) | coming)).any(1)
            noticed_h = nh.any(1)
            nxt = np.where(in_cov, np.where(noticed_h & wf["crouch"], WF_SHELTER, WF_NONE),
                           np.where(((prev == WF_PANIC) & near_h.any(1)) | panic_now, WF_PANIC,
                                    np.where(noticed_h | nr.any(1), WF_ALERT, WF_NONE))).astype(np.int8)
            nxt[~live] = WF_NONE
            # 방향: 도주 = 안전 거리 안 사냥 중인 늑대들, 경계 = 알아챈 늑대들의 반대(거리 역수 가중 합). 0 이면 가장 가까운 그 늑대 반대
            sel = np.where((nxt == WF_PANIC)[:, None], near_h, nh | nr)
            wt = sel / np.maximum(pd, 0.5)
            s = np.stack([-(ex * pinv * wt).sum(1), -(ey * pinv * wt).sum(1)], 1)
            dirs = normalize(s)
            zero = ((nxt == WF_ALERT) | (nxt == WF_PANIC)) & ~((dirs * dirs).sum(1) > EPS * EPS)
            if zero.any():
                j = np.where(sel[zero], pd[zero], np.inf).argmin(1)
                iz = np.flatnonzero(zero)
                dirs[zero] = -np.stack([ex[iz, j], ey[iz, j]], 1) * pinv[iz, j][:, None]
            pan = nxt == WF_PANIC
            to_sh = np.zeros(N, dtype=bool)                       # 은신처 쪽으로 정한 도주(가장자리 굽히기에서 뺀다)
            if pan.any() and len(self.cov_r):
                # 늑대 반대쪽(±acos(shelter_cos)) 은신처가 가장자리 shelter_r 안에 있으면 가장 가까운 그 은신처 중심 쪽으로
                ip = np.flatnonzero(pan)
                vx = self.cov_c[:, 0][None, :] - self.pos[ip, 0:1]
                vy = self.cov_c[:, 1][None, :] - self.pos[ip, 1:2]
                dc = np.sqrt(vx * vx + vy * vy)
                cs = (vx * dirs[ip, 0:1] + vy * dirs[ip, 1:2]) / np.maximum(dc, EPS)
                em = np.where((dc > EPS) & (dc - self.cov_r[None, :] <= wf["shelter_r"]) & (cs >= wf["shelter_cos"]),
                              dc - self.cov_r[None, :], np.inf)
                k = em.argmin(1)
                ar = np.arange(len(ip))
                has = np.isfinite(em[ar, k])
                if has.any():
                    ih, kh = ip[has], k[has]
                    dirs[ih] = np.stack([vx[ar[has], kh], vy[ar[has], kh]], 1) / dc[ar[has], kh][:, None]
                    to_sh[ih] = True
            if wf["edge_r"] > 0.0:
                # 10-16: 가장자리·모서리 굽히기(wf_edge_steer) — 경계·도주(은신처 쪽 도주 말고)
                eg = ((nxt == WF_ALERT) | pan) & ~to_sh & ((dirs * dirs).sum(1) > EPS * EPS)
                if eg.any():
                    dirs[eg] = wf_edge_steer(self.pos[eg], dirs[eg], self.size, wf["edge_r"])
            # 무대 벽 여유 안이면 벽 쪽 성분을 지운다(다 지워지면 그대로) — C++ KeepDirection
            mg, size, p = wf["wall_margin"], self.size, self.pos
            sl = dirs.copy()
            sl[:, 0] = np.where(((p[:, 0] <= mg) & (sl[:, 0] < 0.0)) | ((p[:, 0] >= size - mg) & (sl[:, 0] > 0.0)), 0.0, sl[:, 0])
            sl[:, 1] = np.where(((p[:, 1] <= mg) & (sl[:, 1] < 0.0)) | ((p[:, 1] >= size - mg) & (sl[:, 1] > 0.0)), 0.0, sl[:, 1])
            sl = normalize(sl)
            dirs = np.where(((sl * sl).sum(1) > EPS * EPS)[:, None], sl, dirs)
            dirs[(nxt != WF_ALERT) & (nxt != WF_PANIC)] = 0.0
        over_prev = (prev == WF_PANIC) | (prev == WF_SHELTER)
        rel = over_prev & (nxt != WF_PANIC) & (nxt != WF_SHELTER) & live
        if rel.any():
            rs.lock_left = np.where(rel & (rs.lock_left >= 0), 0, rs.lock_left)
            rs.ev_wait = np.where(rel, -1, rs.ev_wait)
        self._wf_panic_starts += int(np.count_nonzero((nxt == WF_PANIC) & (prev != WF_PANIC)))
        ends = (prev == WF_PANIC) & (nxt != WF_PANIC) & live
        self._wf_panic_ends += int(np.count_nonzero(ends))
        self._wf_panic_end_shelter += int(np.count_nonzero(ends & in_cov))
        self.wf_mode, self.wf_dir = nxt, dirs

    def wild_stats(self) -> dict:
        """야생 1단계 통계 (켠 규칙만, 동역학과 무관). 비축: 산 개체 평균·최솟값, 꺼내 쓴·채운 에너지, 약한 개체-스텝 비율·약한 채 잡힌 수.
        포만: 배부름·먹기 늑대-스텝 비율, 잡은 수, 배부름 스텝. 도주 반사: 실행한 덮기별 산 개체-스텝 비율, 도주 시작·끝·은신처에서 끝."""
        out: dict = {}
        if self._wr is not None:
            live = np.ones(self.N, dtype=bool) if self.alive is None else self.alive
            r = self.reserve[live]
            out.update(reserve_mean=float(r.mean()) if len(r) else float("nan"), reserve_min=float(r.min()) if len(r) else float("nan"),
                       reserve_cap=float(self._wr_cap), reserve_used=self._wr_used, reserve_refill=self._wr_refill,
                       weak_frac=self._wr_weak_n / max(self._wr_live_n, 1), weak_caught_n=self._wr_weak_caught)
        if self._ws is not None:
            n = max(self._ws_steps_n, 1)
            out.update(sated_frac=self._ws_sated_n / n, eating_frac=self._ws_eat_n / n, wolf_kills_n=self._ws_kills_n,
                       sat_steps=self._ws_sat_steps)
        if self._wf is not None:
            tot = max(int(self._wf_mode_n.sum()), 1)
            out.update({f"mode_{k}_frac": int(c) / tot for k, c in zip(WF_MODE_NAMES, self._wf_mode_n)})
            out.update(panic_starts=self._wf_panic_starts, panic_ends=self._wf_panic_ends, panic_end_shelter=self._wf_panic_end_shelter)
        if not out:
            raise ValueError("wild_stats 는 야생 1단계 규칙(wild_*)을 하나라도 켠 세계에만 있다")
        return out

    def _pack_step(self, move, speed, has_target, j, hunting):
        """야생 2단계 2 늑대 무리 협동 (모듈 docstring '야생 2단계' 2). `_step_predators_v3` 가 표적 고르기·잠행형 상태 전이 뒤에 부른다.
        앞장·돕는 늑대를 가르고 `pack_goals` 의 방향으로 돕는 늑대의 move 를 덮는다(속력 = 기다림이면 0, 아니면 기본 속력 pred_speed).
        난수 없음. 반환 (move, speed)."""
        stalker = self.pred_type == PT_STALKER
        wolf = ~self.pred_is_player
        run_now = (has_target & (self.pred_type == PT_CHASER)) | (stalker & (self.stalk_state == ST_POUNCE))
        leader = wolf & run_now & has_target
        helper = wolf & hunting & ~run_now
        self._pack_lead_tgt = np.where(leader, j, -1).astype(np.int64)
        hp, wt, dr, prey, dv = pack_goals(self.pred_pos, self.pred_head, leader, helper, j, self.pos, self.pos - self._pack_p0,
                                          self.cov_c, self.cov_r, self._zw_m, self.size, self._wp)
        self.pack_help, self.pack_wait, self.pack_door, self.pack_prey = hp, wt, dr, prey
        self._wp_steps_n += int(np.count_nonzero(wolf))
        self._wp_lead_n += int(np.count_nonzero(leader))
        self._wp_help_n += int(np.count_nonzero(hp))
        self._wp_wait_n += int(np.count_nonzero(wt))
        self._wp_door_n += int(np.count_nonzero(dr))
        if hp.any():
            move = np.where(hp[:, None], dv, move)
            speed = np.where(hp, np.where(wt, 0.0, self.pred_speed), speed)
        return move, speed

    def obstacle_stats(self) -> dict:
        """야생 2단계 3 세로 장애물 통계 (통계 전용, 모듈 docstring '야생 2단계' 3). n = 원판 수, area_frac = 원판 넓이 합 ÷ 무대 넓이(겹침은 두 번),
        deer_hit·deer_back = 원판에 부딪혀 미끄러진·되돌린 사슴-스텝(deer_steps 가운데), wolf_hit·wolf_back·wolf_dead = 늑대-스텝(부딪힘·되돌림·돌아섬),
        eye_pairs·eye_blocked = 사슴이 시야(반경·각)로 본 위협 쌍과 그중 원판이 가린 쌍(스텝 관측), tgt_pairs·tgt_blocked = 늑대가 시야로 본 사슴 쌍과
        그중 가린 쌍, push_moved·push_failed = 원판 밖으로 옮긴·못 옮긴 개체(reset·리스폰). 켜지 않은 세계는 ValueError."""
        if self._ob is None:
            raise ValueError("obstacle_stats 는 obstacles 를 켠 세계에서만 센다")
        d = self.obstacles

        def ratio(x, y):
            return float(x) / float(y) if y else 0.0

        return dict(n=int(len(d)), area_frac=ratio(float(np.pi * (d[:, 2] * d[:, 2]).sum()), self.size * self.size),
                    r_mean=float(d[:, 2].mean()) if len(d) else 0.0,
                    deer_steps=self._ob_deer_steps, deer_hit=self._ob_deer_hit, deer_back=self._ob_deer_back,
                    wolf_steps=self._ob_wolf_steps, wolf_hit=self._ob_wolf_hit, wolf_back=self._ob_wolf_back, wolf_dead=self._ob_wolf_dead,
                    eye_pairs=self._ob_eye_pairs, eye_blocked=self._ob_eye_blocked, eye_blocked_frac=ratio(self._ob_eye_blocked, self._ob_eye_pairs),
                    tgt_pairs=self._ob_tgt_pairs, tgt_blocked=self._ob_tgt_blocked, tgt_blocked_frac=ratio(self._ob_tgt_blocked, self._ob_tgt_pairs),
                    push_moved=self._ob_push_moved, push_failed=self._ob_push_failed)

    def pack_stats(self) -> dict:
        """야생 2단계 2 늑대 무리 협동 통계 (통계 전용). 늑대-스텝 wolf_steps 가운데 앞장(lead)·도움(help)·기다림(wait)·은신처 문(door) 수와 몫,
        늑대 포획 catches 와 그 가운데 다른 앞장 늑대도 쫓던 사슴을 잡은 협동 포획 pack_catches. wild_pack 을 켠 세계에만 있다."""
        if self._wp is None:
            raise ValueError("pack_stats 는 wild_pack 을 켠 세계에만 있다")
        n = max(self._wp_steps_n, 1)
        return dict(wolf_steps=self._wp_steps_n, lead_n=self._wp_lead_n, help_n=self._wp_help_n, wait_n=self._wp_wait_n,
                    door_n=self._wp_door_n, lead_frac=self._wp_lead_n / n, help_frac=self._wp_help_n / n,
                    catches=self._wp_catch_n, pack_catches=self._wp_pack_catch_n)

    def hunt_stats(self) -> dict:
        """야생 2단계 사냥 성공률 (모듈 docstring '야생 2단계', 통계 전용). 늑대(플레이어형 위협 말고) 모두와 유형별(chaser·stalker):
        starts·ends·success·outside(사냥 밖 포획) 수와 rate = success / ends(끝난 사냥이 없으면 nan). 아직 이어지는 사냥은 ends 에 없다(ongoing).
        v3 포식자 스텝(repertoire·threats 중 하나라도 켠 세계)에만 있다."""
        if not self._v3p:
            raise ValueError("hunt_stats 는 v3 포식자 스텝(repertoire·threats)을 켠 세계에만 있다")
        n = self._hunt_n
        out: dict = {}
        for tag, cols in (("", slice(0, 2)), ("chaser_", slice(PT_CHASER, PT_CHASER + 1)), ("stalker_", slice(PT_STALKER, PT_STALKER + 1))):
            v = n[:, cols].sum(1)
            out.update({f"{tag}{k}": int(x) for k, x in zip(HUNT_KEYS, v)})
            out[f"{tag}rate"] = float(v[2]) / float(v[1]) if v[1] > 0 else float("nan")
        out["ongoing"] = int(np.count_nonzero(self._hunt_on))
        return out

    # ------------------------------------------------------------------ #
    # 통계 (§7.2)
    # ------------------------------------------------------------------ #

    def _reset_stats(self) -> None:
        self._rew_total = 0.0
        self._repro_total = 0
        self._pred_deaths = 0
        self._starve_deaths = 0   # §7.2 열은 아니고 경제 보정용 진단 카운터
        self._life_sum = 0
        self._life_count = 0
        self._life_cur = np.zeros(self.N, dtype=np.int64)
        # repertoire 세계의 v1 행동 열 합은 0 자리(행동이 'behavior' 한 열이라 v1 stats 의 조향 열이 없다)
        self._act_sum = np.zeros(ACT_DIM if self._rp is not None else self.act_dim)
        self._flee_sq = 0.0
        self._cover_steps = 0
        self._agent_steps = 0
        self._a_pred = np.zeros(3)   # cohesion, flee_dist, cover — 포식자 보일 때
        self._n_pred = 0
        self._a_nopred = np.zeros(3)
        self._n_nopred = 0
        self._f_hungry, self._n_hungry = 0.0, 0
        self._f_full, self._n_full = 0.0, 0
        # 야생 2단계 사냥 성공률 (hunt_stats): [시작·끝·성공·사냥 밖 포획] × 위협 유형 [추격형·잠행형·플레이어] 늑대 수. v3 포식자 스텝만 센다
        self._hunt_n = np.zeros((len(HUNT_KEYS), 3), dtype=np.int64)
        if self._sp is not None:     # v2.1 보행 지표 (gait_stats). 모두 개체-스텝 수다
            # 개체-스텝 히스토그램 [경계 2, 실제 보행 3, 명령 보행 3, 포식자 거리 구간 4, 배부름 2]. 거리 구간은
            # [안 보임, d<0.25, 0.25≤d<0.5, d≥0.5] (d = d_pred/see_r), 배부름은 [energy<0.5, ≥0.5] (결정 때).
            # 경계 축은 [비경계, 경계]이고 vigilance 를 끈 세계는 모두 비경계 칸이다(v2.1 과 같은 수)
            self._gait_hist = np.zeros((2,) + GAIT_HIST_SHAPE, dtype=np.int64)
            self._sw = np.zeros(2, dtype=np.int64)            # 보행 전환 수 [실제, 명령] (B8)
            self._sw_steps = 0                                # 직전 스텝이 같은 개체인 개체-스텝
            self._gait_prev = np.full((2, self.N), -1, dtype=np.int8)   # 직전 [실제, 명령] 보행, −1 = 없음
            self._intake_sum = 0.0                            # 먹이로 얻은 에너지(상한에서 잘린 몫 제외)
            self._drain_sum = 0.0                             # 대사로 쓴 에너지
        if self._vg is not None:     # v2.2 경계 지표 (vigil_stats). 모두 개체-스텝 수·합이다
            self._vig_hist = np.zeros(VIG_HIST_SHAPE, dtype=np.int64)   # [구간 4, 결정 관측 시야 2, 배부름 2, 경계 2]
            self._vig_esum = np.zeros(4)               # B5 회귀: Σe, Σe², Σv, Σe·v (e = 결정 때 관측 4, v = 경계 0/1)
            self._vig_ema: list[float] = []            # B5′: 스텝마다 결정 때 관측 5(전역 값)와 경계 개체 수
            self._vig_ema_n: list[int] = []
            self._vig_kin = np.zeros(2)                # 결정 관측 시야별 동족 수·포식자 수 합 (360° 해석용, 4.2)
            self._vig_pc = np.zeros(2)
            self._vig_threat = 0.0                     # 결정 때 threat_recency 합
            self._vig_truth = np.zeros(VIG_TRUTH_SHAPE, dtype=np.int64)   # [기준 구간 3, 경계 2] (*_truth 열)
            # B4 [이동 도주·결정 관측 기본 FOV, 이동 도주·결정 관측 경계 시야, 경계한 도주 분기] × [표본, 다음 관측 안 보임]
            self._b4 = np.zeros((3, 2), dtype=np.int64)
            self._vsw, self._vsw_steps = 0, 0          # 경계 전환 수, 직전 스텝이 같은 개체인 개체-스텝
            self._vig_prev = np.full(self.N, -1, dtype=np.int8)
        if self._vw is not None:     # v2.2r 창 지표 (window_stats). 개체-스텝 수다
            self._win_hist = np.zeros(WINDOW_HIST_SHAPE, dtype=np.int64)   # [구간 3, 배부름 2, 실제 정지 2, 경계 2]
            self._win_look = 0                         # 반사 돌아보기가 돈 개체-스텝
        if self._dn is not None:     # v2.4 위상 지표 (daynight_stats). 위상 구간은 결정 때 어둠 d 다
            self._dn_hist = np.zeros(DN_HIST_SHAPE, dtype=np.int64)
            self._dn_b = np.zeros(DN_B_SHAPE, dtype=np.int64)
            self._dn_dead = np.zeros((2, 3), dtype=np.int64)    # [피식, 아사] × 위상
            self._dn_energy = np.zeros((2, 3))                  # [먹이 에너지, 대사] × 위상
            self._dn_dark = 0.0                                 # 스텝별 d 합
            self._dn_steps = 0
            if self._rp is not None:     # v3: 휴식·먹기 열의 행동 기준 판 [위상 3, 배부름 2, 결정 때 은신처 안 2, 먹이 셀 2, 행동]
                self._dn_rep = np.zeros((3, 2, 2, 2, rep.N_BEHAVIORS), dtype=np.int64)
        if self._rp is not None:     # v3 레퍼토리 지표 (repertoire_stats). 개체-스텝 수다
            self._rep_hist = np.zeros((3, 2, rep.N_BEHAVIORS), dtype=np.int64)   # [위상(낮·박명·밤), 위협 보임, 행동]
            self._rep_dead = np.zeros((2, rep.N_BEHAVIORS), dtype=np.int64)      # [피식, 아사] × 죽은 스텝의 행동
            self._rep_switch, self._rep_decide, self._rep_flicker = 0, 0, 0
            self._rep_before = np.full(self.N, -1, dtype=np.int64)              # 마지막 전환 전 행동(없으면 −1)
            self._rep_last_sw = np.full(self.N, -(10 ** 9), dtype=np.int64)     # 마지막 전환 스텝
            self._rep_flicker_w = int(FLICKER_SECONDS * 60.0 / float(self.cfg.policy_interval))
            self._rep_sw_slot = np.zeros(self.N, dtype=np.int64)                # 슬롯별 전환·깜빡임 수 (rep_slot_counts)
            self._rep_flick_slot = np.zeros(self.N, dtype=np.int64)
        if self._th is not None:     # v3 위협 지표 (threats_stats)
            self._th_catch = np.zeros(4, dtype=np.int64)    # 포획 수 [근접 추격, 원거리 추격, 잠행, 플레이어]
            self._th_pounce = np.zeros(2, dtype=np.int64)   # [돌진 시작, 돌진 포획]
            self._th_charge = 0                             # 플레이어 돌진 시작
        if self._sd is not None:     # v3 R2 M7 지표 (stare_stats). 수다
            self._sd_standoff_n = self._sd_break_n = self._sd_blink_n = self._sd_balk_n = 0
            self._sd_spotted_n = self._sd_spotted_charge_n = self._sd_spotted_charge_catch_n = 0
            self._sd_lock_steps = self._sd_lock_n = self._sd_stare_steps = 0
            self._sd_break_t = np.full(self.N, -(10 ** 9), dtype=np.int64)     # 개체별 마지막으로 대치가 깨진 스텝
            self._sd_break_beh_n = self._sd_charge_catch_n = 0   # 표적이 행동을 바꿔 깬 대치, 들키지 않은 돌진의 포획
        if self._al is not None:     # v3 R2 M8 지표 (alarm_stats). 수·합이고 동역학과 무관하다
            N = self.N
            self._al_emit_n = np.zeros(3, dtype=np.int64)  # 방출 [홉 0, 1, 2 이상]
            self._al_cry = self._al_listen = self._al_emitters = 0
            self._al_with = self._al_with_unseen = 0
            self._al_e7_n = self._al_e7_sw = self._al_e7_dn = 0
            self._al_e7_t = np.full(N, -(10 ** 9), dtype=np.int64)
            self._al_e7_dt = np.full(N, -(10 ** 9), dtype=np.int64)     # e7_decide_frac 용(결정 시점이 오면 지운다)
            self._al_entry = np.zeros(rep.N_BEHAVIORS, dtype=np.int64)
            self._al_entry_heard = np.zeros(rep.N_BEHAVIORS, dtype=np.int64)
            self._al_gap_sum = self._al_gap_n = 0
            self._al_onset_t = np.full(N, -1, dtype=np.int64)
            self._al_dir_n = self._al_dir_pt = self._al_dir_cp = 0
            # 물결: 홉 0 방출마다 원점 번호를 주고 중계·수신이 그 번호를 잇는다(개체가 쥔 경보의 원점 _al_src, 없으면 −1)
            self._al_src = np.full(N, -1, dtype=np.int64)
            self._al_next_src = self._al_h0 = self._al_wave_hits = 0
            self._al_wave_last = np.full(N, -1, dtype=np.int64)
            self._al_heads: list = []                       # (확인 스텝, 개체, 세대) — 1초 안 고개 든 비율
            self._al_heads_n = self._al_heads_up = self._al_heads16_n = self._al_heads16_up = 0
            self._al_seen0 = self._al_false = 0
        if self._rz:                 # v3 현실성 지표 (realism_stats). 수이고 동역학과 무관하다
            self._rz_obs_n = self._rz_rear_n = self._rz_heard_n = 0
            self._zs_safe_n = self._zs_saved_n = self._zs_steps = 0
            self._zf_in = self._zf_all = 0.0
            self._zn_dark_n = self._zn_dark_awake = self._zn_settle_n = self._zn_abort_n = self._zn_onset_n = 0
            self._zn_block_deer_n = self._zn_block_hunt_n = self._zn_wake_n = 0
        if self._r3:                 # v3 R3 지표 (r3_stats). 수이고 동역학과 무관하다
            self._zc_lock_n = self._zc_held = self._zc_lost = 0
            self._zc_rel_cover = self._zc_rel_lost = self._zc_rel_state = 0
            self._zc_rel_catch = self._zc_catch_own = self._zc_rel_dead = 0
            self._zw_push_n = self._zw_slide_n = self._zw_stuck_n = self._zw_giveup_n = self._zw_inside_n = 0
            nt = len(TERRAIN_NAMES)
            self._zt_deer = np.zeros(nt, dtype=np.int64)
            self._zt_catch = np.zeros(nt, dtype=np.int64)
            self._zt_pounce = np.zeros(nt, dtype=np.int64)
            self._zt_pounce_hit = np.zeros(nt, dtype=np.int64)
            self._zt_pounce_tc = np.zeros(self.M, dtype=np.int64)     # 돌진 중인 잠행형의 돌진 시작 때 표적의 땅

    def _accumulate(self, a, rew, repro, caught, starved, done) -> None:
        self._rew_total += float(rew.sum())
        self._repro_total += int(repro.sum())
        self._pred_deaths += int(caught.sum())
        self._starve_deaths += int(starved.sum())
        self._life_cur += 1
        if done.any():
            self._life_sum += int(self._life_cur[done].sum())
            self._life_count += int(done.sum())
            self._life_cur[done] = 0
        self._agent_steps += self.N
        self._act_sum += a.sum(0)
        self._flee_sq += float((a[:, 2] ** 2).sum())
        self._cover_steps += int(self._g["in_cover"].sum())

        seen = self._g["pred_count"] > 0
        cols = a[:, [1, 2, 3]]
        self._a_pred += cols[seen].sum(0)
        self._n_pred += int(seen.sum())
        self._a_nopred += cols[~seen].sum(0)
        self._n_nopred += int((~seen).sum())

        hungry = self.energy < 0.5 * self.cfg.max_energy
        self._f_hungry += float(a[hungry, 0].sum())
        self._n_hungry += int(hungry.sum())
        self._f_full += float(a[~hungry, 0].sum())
        self._n_full += int((~hungry).sum())

    def _gait_accumulate(self, e_prev: np.ndarray, intake: np.ndarray, drain: np.ndarray) -> None:
        """v2.1 보행 지표를 센다. `step` 이 `_accumulate` 바로 뒤, 관측을 새로 계산하기 전에 부른다.

        조건(포식자 거리, 배고픔)은 정책이 이번 행동을 고를 때 본 상태다: 스텝 전 기하 `self._g`, 스텝 전 에너지
        `e_prev`(리스폰 직후 개체는 init_energy, 관측 4 와 같다). B1·B2 는 명령 보행으로 잰다 — 상태를 안 보는
        상수·순열 대조군에서 조건부 차이가 구성상 0 이 되게 한다(계획서 6.3 판정 규칙). 방향이 없어 실제로는
        멈춘 몫은 stall_frac 로 따로 낸다. v2.2 는 경계 축을 앞에 둔다(경계한 개체의 실제 보행은 정지다).
        """
        cfg = self.cfg
        g, cmd = self.gait, self.gait_cmd
        d = self._g["d_pred_min"] / cfg.see_r                  # 안 보이면 inf
        # 거리 구간: 안 보임 0, [0, 0.25) 1, [0.25, 0.5) 2, [0.5, 1] 3 (inf 는 두 문턱을 넘지만 seen 이 0 으로 만든다)
        b = (d < np.inf) * (1 + (d >= B1_EDGES[0]) + (d >= B1_EDGES[1]))
        full = e_prev >= HUNGRY * cfg.max_energy               # False 배고픔, True 배부름
        code = ((g * 3 + cmd) * 4 + b) * 2 + full               # GAIT_HIST_SHAPE 의 C 순서 평탄 인덱스
        if self._vg is not None:                                # 경계 축 (끈 세계는 모두 0 칸 — v2.1 과 같은 수)
            code = code + self.vigilant * int(np.prod(GAIT_HIST_SHAPE))
        self._gait_hist += np.bincount(code, minlength=self._gait_hist.size).reshape(self._gait_hist.shape)

        prev = self._gait_prev
        same = prev[0] >= 0
        self._sw_steps += int(np.count_nonzero(same))
        self._sw[0] += np.count_nonzero(same & (prev[0] != g))
        self._sw[1] += np.count_nonzero(same & (prev[1] != cmd))
        prev[0] = g
        prev[1] = cmd

        self._intake_sum += float(intake.sum())
        self._drain_sum += float(drain.sum())

    def gait_stats(self) -> dict:
        """v2.1 보행 통계 — reset 뒤 누적 (v1 `stats()` 10열 밖, 계획서 4.8). Gate E1 과 B1·B2·B8 이 쓴다.

        열 순서는 `GAIT_STAT_COLUMNS`. 비율은 모두 개체-스텝 기준이다. 분모가 0 인 열은 nan 이다.
        - stop_frac·walk_frac·run_frac: 실제 보행 비율(v2.2 경계는 속력 0 이라 정지에 든다. 경계 비율은 vigil_stats).
          stall_frac: 경계가 아닌데 명령은 이동이고 방향이 없어 정지한 비율
        - stop_frac_cmd·walk_frac_cmd·run_frac_cmd: 명령 보행(행동 idx 4 의 문턱) 비율. 경계 여부와 무관한 speed 명령이다
        - hungry_frac: 결정 때 energy < 0.5 인 비율 (Gate E1 (a) "energy<0.5 스텝")
        - starve_rate: 아사 / 개체-스텝, starve_share: 아사 / 사망 (env_v2/rollout.py 와 같은 정의)
        - b1 = P(뛰기 | 보임 & d < 0.5·see_r) − P(뛰기 | 안 보임). p_run_unseen, p_run_d025 [0, 0.25),
          p_run_d050 [0.25, 0.5), p_run_d100 [0.5, 1] (× see_r) 은 거리 구간별 P(뛰기) (6.2 B1). '뛰기' = 경계가 아니고
          명령이 뛰기(v2.2 는 경계가 speed 보다 우선이라 경계 개체는 뛰지 않는다). 분모는 경계 개체를 포함한다
        - b2 = P(정지 | 배고픔) − P(정지 | 배부름), p_stop_hungry·p_stop_full (6.2 B2 '경계가 아닌 정지': 경계가 아니고
          명령이 정지. v2.1 은 경계가 없어 모든 정지가 여기에 든다)
        - b8·b8_cmd: 개체당 초당 보행 전환 수(실제·명령). 직전 스텝이 같은 개체인 스텝만 센다. 1스텝 =
          policy_interval/60 초 (replay_v2.step_seconds 와 같은 정의, §9.7)
        - intake_per_step·drain_per_step: 개체-스텝당 먹이 에너지·대사
        vigilance 를 끈 세계는 경계 칸이 비어 v2.1 과 같은 값이다(정수 합).
        """
        if self._sp is None:
            raise ValueError("gait_stats 는 speed 를 켠 세계에만 있다 (끈 세계는 v1 과 같이 늘 herb_speed 로 움직인다)")
        nan = float("nan")
        n = self._agent_steps
        H = self._gait_hist.sum(0)                             # [실제, 명령, 거리 구간, 배부름] — 모든 개체
        H0 = self._gait_hist[0]                                # 같은 모양 — 경계가 아닌 개체

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        gait_n, cmd_n = H.sum((1, 2, 3)), H.sum((0, 2, 3))
        b1_n, b1_run = H.sum((0, 1, 3)), H0[:, GAIT_RUN].sum((0, 2))
        b2_n, b2_stop = H.sum((0, 1, 2)), H0[:, GAIT_STOP].sum((0, 1))
        stall = H0[GAIT_STOP, GAIT_WALK:].sum()
        p_run = [ratio(b1_run[k], b1_n[k]) for k in range(4)]
        near = ratio(b1_run[1] + b1_run[2], b1_n[1] + b1_n[2])
        p_stop = [ratio(b2_stop[k], b2_n[k]) for k in range(2)]
        deaths = self._pred_deaths + self._starve_deaths
        per_sec = 60.0 / float(self.cfg.policy_interval)
        out = dict(
            stop_frac=ratio(gait_n[0], n), walk_frac=ratio(gait_n[1], n),
            run_frac=ratio(gait_n[2], n), stall_frac=ratio(stall, n),
            stop_frac_cmd=ratio(cmd_n[0], n), walk_frac_cmd=ratio(cmd_n[1], n),
            run_frac_cmd=ratio(cmd_n[2], n),
            hungry_frac=ratio(b2_n[0], n),
            starve_rate=self._starve_deaths / max(self.t * self.N, 1),
            starve_share=ratio(self._starve_deaths, deaths),
            b1=near - p_run[0], p_run_unseen=p_run[0], p_run_d025=p_run[1], p_run_d050=p_run[2],
            p_run_d100=p_run[3],
            b2=p_stop[0] - p_stop[1], p_stop_hungry=p_stop[0], p_stop_full=p_stop[1],
            b8=ratio(self._sw[0], self._sw_steps) * per_sec, b8_cmd=ratio(self._sw[1], self._sw_steps) * per_sec,
            intake_per_step=ratio(self._intake_sum, n), drain_per_step=ratio(self._drain_sum, n),
        )
        assert tuple(out) == GAIT_STAT_COLUMNS
        return out

    def _vigil_accumulate(self, a: np.ndarray, e_prev: np.ndarray, ema0: float, moving: np.ndarray):
        """v2.2 경계 지표를 센다. `step` 이 `_accumulate` 뒤, 다음 관측의 시야(8a)와 관측(8)을 바꾸기 전에 부른다.

        조건은 정책이 이번 행동을 고를 때 본 상태다: 스텝 전 기하 `self._g`(포식자 수·동족 수), 결정 때 threat_recency
        (`self.threat`, 관측 7), 결정 관측의 시야(`self._wide`), 결정 때 에너지 `e_prev`(관측 4), 관측 5 `ema0`.
        경계는 이번 스텝에 적용된 `self.vigilant`(행동의 문턱이라 상수·순열 대조군에서 조건부 차이가 구성상 0).
        시야와 무관한 기준 구간은 결정 관측 때 저장한 `self._near`·`self._tr_truth`(`_perceive`)로 정한다 — 스텝이
        위치를 옮긴 뒤 다시 재지 않는다.
        반환: B4 표본 마스크 (이동 도주·결정 관측 기본 FOV, 이동 도주·결정 관측 경계 시야, 경계한 도주 분기) — 다음
        관측을 계산한 뒤 `_b4_accumulate` 가 센다.
        """
        cfg = self.cfg
        g, vig = self._g, self.vigilant
        pc = g["pred_count"]
        seen = pc > 0
        recent = ~seen & (self.threat > RECENT_THREAT)
        seg = np.where(seen, 2 + (pc >= 2), recent)            # 0 평시, 1 최근 위협·안 보임, 2 한 마리 보임, 3 둘 이상
        wide = self._wide
        full = e_prev >= HUNGRY * cfg.max_energy
        code = ((seg * 2 + wide) * 2 + full) * 2 + vig          # VIG_HIST_SHAPE 의 C 순서 평탄 인덱스
        self._vig_hist += np.bincount(code, minlength=self._vig_hist.size).reshape(VIG_HIST_SHAPE)
        e = np.clip(e_prev / cfg.max_energy, 0.0, 1.0)
        vf = vig.astype(np.float64)
        self._vig_esum += (e.sum(), (e * e).sum(), vf.sum(), (e * vf).sum())
        self._vig_ema.append(float(ema0))
        self._vig_ema_n.append(int(np.count_nonzero(vig)))
        self._vig_kin += np.bincount(wide, weights=g["kin_count"], minlength=2)
        self._vig_pc += np.bincount(wide, weights=pc, minlength=2)
        self._vig_threat += float(self.threat.sum())
        seg_t = np.where(self._near, 2, self._tr_truth > RECENT_THREAT)   # 0 평시, 1 최근 반경 안·지금 밖, 2 반경 안
        self._vig_truth += np.bincount(seg_t * 2 + vig, minlength=self._vig_truth.size).reshape(VIG_TRUTH_SHAPE)
        prev = self._vig_prev
        same = prev >= 0
        self._vsw_steps += int(np.count_nonzero(same))
        self._vsw += int(np.count_nonzero(same & (prev != vig)))
        prev[:] = vig
        branch = g["d_pred_min"] < a[:, 2] * cfg.see_r          # 도주 분기 (steer 와 같은 식)
        mv = branch & ~vig & moving
        return mv & ~wide, mv & wide, branch & vig

    def _b4_accumulate(self, flee: tuple, g_next: dict, done: np.ndarray) -> None:
        """B4: 도주 표본(`_vigil_accumulate` 의 마스크 3개) 중 다음 관측(스텝 끝 8)에서 포식자가 안 보인 수.
        이번 스텝에 죽은 개체는 뺀다."""
        lost = g_next["pred_count"] == 0
        for k, m in enumerate(flee):
            m = m & ~done
            self._b4[k, 0] += int(np.count_nonzero(m))
            self._b4[k, 1] += int(np.count_nonzero(m & lost))

    def vigil_stats(self) -> dict:
        """v2.2 경계 통계 — reset 뒤 누적 (v1 `stats()` 10열 밖, 계획서 4.8). Gate E2 와 B3·B4·B5·B5′ 이 쓴다.

        열 순서는 `VIGIL_STAT_COLUMNS`. 비율은 개체-스텝 기준이다(B4 는 표본 기준). 분모가 0 인 열은 nan 이다.
        구간(결정 때): 보임 = 포식자 수 > 0, 최근 위협 = 안 보임 & threat_recency > RECENT_THREAT(0.5), 평시 = 그 밖.

        주의 — 360° 치우침 (계획서 4.2 '360° 경계 중에는 kin_count·pred_count 도 늘어나므로 B 지표를 따로 본다',
        10-03 검토): 경계한 개체의 다음 결정 관측은 360° 라 '보임'·'최근 위협' 구간에 더 자주 든다. 그래서 경계가
        몇 스텝 이어지기만 하면(포식자를 전혀 보지 않는 정책이어도) 관측 구간으로 나눈 P(경계) 차가 행동이 아니라
        시야 때문에 커진다. 상수 정책·C1′(같은 스텝 개체끼리 행동 순열)는 경계의 지속을 끊어 이 치우침이 없으므로
        6.3 (1) 의 '대조군에서 구성상 0' 전제가 경계 지표에는 성립하지 않는다. 시야를 합친 b3·b5p_pred·p_vig_seen·
        p_vig_pc*·b4 는 기술용이고, 판정 후보는 *_narrow(결정 관측이 기본 FOV)·*_truth(시야와 무관한 기준 구간)다.
        1차 정의는 1-6 사전 등록에서 정한다. *_narrow 도 직전 한 스텝만 거른다 — threat 흔적을 통한 360° 선택 효과
        (예: 배고플수록 자주 경계하는 정책은 배고픈 개체가 최근 360° 로 포식자를 봐 '최근 위협'에 더 들고, 경계를
        시작하기도 쉽다)는 남는다. *_truth 는 시야 효과를 빼지만 경계가 위치(정지)를 통해 반경 안 여부를 바꾸는
        동역학 경로는 남는다.

        - vig_frac: 경계 비율. seg_*_frac: 구간 비율. p_vig_seen·p_vig_recent·p_vig_calm: 구간별 P(경계) (시야 합침)
        - b3 = P(경계 | 최근 위협·안 보임) − P(경계 | 평시) (6.2 B3, 시야 합침 — 경계 지속이 '최근 위협' 표본을 늘려
          치우친다). b3_narrow: 결정 관측이 기본 FOV 인 개체만(직전 스텝에 경계하지 않은 개체 — 경계를 '시작'하는 쪽)
        - b4 = 이동 도주(도주 분기 & 경계 아님 & 이번 스텝에 움직임) 중 다음 관측에서 포식자를 놓친 비율 (6.2 B4,
          시야 합침). b4_narrow: 그중 결정 관측이 기본 FOV 인 표본(결정·다음 관측 모두 120°) — **v1 기준선 59.1%
          (v1 은 늘 120°)와 비교하는 값은 b4_narrow 다.** b4_wide: 결정 관측이 경계 시야인 표본(직전 스텝 경계, 뒤쪽
          포식자로도 도주 분기에 들어가 다음 120° 관측에서 구성상 자주 놓친다. 보고만). b4_vig: 도주 분기에서 경계한
          개체가 놓친 비율. *_n 은 표본 수(죽은 개체 제외, b4_n = b4_narrow_n + b4_wide_n)
        - b5 = 결정 때 energy(관측 4)에 대한 경계(0/1) 최소제곱 기울기 (6.2 B5, 기대 −). p_vig_hungry·p_vig_full:
          energy < 0.5 / ≥ 0.5 의 P(경계). **관측적 기울기다(기술용).** 경계는 섭식 0 이라 경계를 이어 간 개체는
          energy 가 내려가고, 직전 뛰기(섭식 0·고대사)도 같은 쪽이다 — energy 를 보지 않는 지속·위협 반응 경계도
          b5 < 0 이 된다(역인과, 기대 부호와 같은 쪽이라 부호 기준이 자동 통과한다). 판정은 C4-energy(관측 4 고정·
          순열) 대비 차 또는 개입 곡선(diagnose_v2.intervention_curve, 관측 4)으로 한다(1-6 사전 등록)
        - B5′ (6.2, 기대 +. 1차로 쓸 정의는 1-6 사전 등록에서 정한다): b5p_pred = P(경계 | 포식자 보임) −
          P(경계 | 안 보임) (관측 기준, 360° 선택 효과 포함 — 포식자를 보지 않는 지속 경계도 + 로 치우친다),
          p_vig_pc0·pc1·pc2 = 포식자 0 / 1 / 2마리 이상일 때 P(경계). b5p_ema = recent_predation(관측 5, 전역 값) 상위
          20% 스텝 − 하위 20% 스텝의 P(경계) (스텝 분위수, diagnose_v2 '위험 높음/낮음'과 같은 분할. 전역 값이라 개체의
          시야와 무관하다)
        - *_narrow (결정 관측이 기본 FOV 인 개체만, 위 구간 그대로): p_vig_seen_narrow, p_vig_pc0_narrow·pc1·pc2,
          b5p_pred_narrow = p_vig_seen_narrow − p_vig_pc0_narrow
        - *_truth (시야와 무관한 기준 구간, 결정 때): 반경 안 = 결정 관측 위치에서 거리 ≤ see_r 인 포식자가 있다(FOV
          무시), 최근 = 반경 밖 & 흔적 > RECENT_THREAT(흔적은 threat_recency 와 같은 규칙·decay 를 반경 안 여부에
          적용한 통계 전용 값, 리스폰 0), 평시 = 그 밖. seg_near_truth_frac·seg_recent_truth_frac: 구간 비율,
          p_vig_near_truth·p_vig_recent_truth·p_vig_calm_truth: 구간별 P(경계), b3_truth = P(경계 | 최근) − P(경계 | 평시),
          b5p_truth = P(경계 | 반경 안) − P(경계 | 반경 밖)
        - b8_vig: 개체당 초당 경계 전환(켜기·끄기) 수. 직전 스텝이 같은 개체인 스텝만 센다(gait b8 과 같은 규칙)
        - 360° 해석용 (계획서 4.2 '경계 중에는 kin_count 와 pred_count 도 늘어난다'): obs_wide_frac = 결정 관측이 경계
          시야였던 비율, kin_narrow·kin_wide·pred_narrow·pred_wide = 시야별 평균 동족 수·포식자 수(관측 정규화 전)
        - threat_mean: 결정 때 threat_recency 평균
        """
        if self._vg is None:
            raise ValueError("vigil_stats 는 vigilance 를 켠 세계에만 있다")
        nan = float("nan")
        H = self._vig_hist                                      # [구간, 시야, 배부름, 경계]
        n = int(H.sum())

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        seg_n, seg_v = H.sum((1, 2, 3)), H[..., 1].sum((1, 2))
        nar_n, nar_v = H[:, 0].sum((1, 2)), H[:, 0, :, 1].sum(1)
        full_n, full_v = H.sum((0, 1, 3)), H[..., 1].sum((0, 1))
        wide_n = H.sum((0, 2, 3))
        p_calm, p_recent = ratio(seg_v[0], seg_n[0]), ratio(seg_v[1], seg_n[1])
        p_seen = ratio(seg_v[2] + seg_v[3], seg_n[2] + seg_n[3])
        p_pc0 = ratio(seg_v[0] + seg_v[1], seg_n[0] + seg_n[1])
        se, see, sv, sev = self._vig_esum
        var = see - se * se / n if n else 0.0
        b5 = (sev - se * sv / n) / var if n and var > 0.0 else nan
        ema = np.asarray(self._vig_ema)
        if len(ema):
            nv = np.asarray(self._vig_ema_n, dtype=np.float64)
            lo, hi = np.quantile(ema, [EMA_SPLIT_Q, 1.0 - EMA_SPLIT_Q])
            m_hi, m_lo = ema >= hi, ema <= lo
            b5p_ema = nv[m_hi].sum() / (self.N * m_hi.sum()) - nv[m_lo].sum() / (self.N * m_lo.sum())
        else:
            b5p_ema = nan
        per_sec = 60.0 / float(self.cfg.policy_interval)
        p_seen_n = ratio(nar_v[2] + nar_v[3], nar_n[2] + nar_n[3])
        p_pc0_n = ratio(nar_v[0] + nar_v[1], nar_n[0] + nar_n[1])
        B = self._b4                                            # [120° 결정 이동 도주, 360° 결정 이동 도주, 경계] × [표본, 놓침]
        T = self._vig_truth                                     # [기준 구간, 경계]
        tn, tv = T.sum(1), T[:, 1]
        p_t = [ratio(tv[k], tn[k]) for k in range(3)]           # 평시, 최근, 반경 안
        out = dict(
            vig_frac=ratio(seg_v.sum(), n),
            seg_seen_frac=ratio(seg_n[2] + seg_n[3], n), seg_recent_frac=ratio(seg_n[1], n),
            seg_calm_frac=ratio(seg_n[0], n),
            p_vig_seen=p_seen, p_vig_recent=p_recent, p_vig_calm=p_calm, b3=p_recent - p_calm,
            b3_narrow=ratio(nar_v[1], nar_n[1]) - ratio(nar_v[0], nar_n[0]),
            b4=ratio(B[0, 1] + B[1, 1], B[0, 0] + B[1, 0]), b4_n=float(B[0, 0] + B[1, 0]),
            b4_vig=ratio(B[2, 1], B[2, 0]), b4_vig_n=float(B[2, 0]),
            b5=b5, p_vig_hungry=ratio(full_v[0], full_n[0]), p_vig_full=ratio(full_v[1], full_n[1]),
            b5p_pred=p_seen - p_pc0, p_vig_pc0=p_pc0, p_vig_pc1=ratio(seg_v[2], seg_n[2]),
            p_vig_pc2=ratio(seg_v[3], seg_n[3]), b5p_ema=float(b5p_ema),
            b8_vig=ratio(self._vsw, self._vsw_steps) * per_sec,
            obs_wide_frac=ratio(wide_n[1], n),
            kin_narrow=ratio(self._vig_kin[0], wide_n[0]), kin_wide=ratio(self._vig_kin[1], wide_n[1]),
            pred_narrow=ratio(self._vig_pc[0], wide_n[0]), pred_wide=ratio(self._vig_pc[1], wide_n[1]),
            threat_mean=ratio(self._vig_threat, n),
            p_vig_seen_narrow=p_seen_n, p_vig_pc0_narrow=p_pc0_n, p_vig_pc1_narrow=ratio(nar_v[2], nar_n[2]),
            p_vig_pc2_narrow=ratio(nar_v[3], nar_n[3]), b5p_pred_narrow=p_seen_n - p_pc0_n,
            b4_narrow=ratio(B[0, 1], B[0, 0]), b4_narrow_n=float(B[0, 0]),
            b4_wide=ratio(B[1, 1], B[1, 0]), b4_wide_n=float(B[1, 0]),
            seg_near_truth_frac=ratio(tn[2], n), seg_recent_truth_frac=ratio(tn[1], n),
            p_vig_near_truth=p_t[2], p_vig_recent_truth=p_t[1], p_vig_calm_truth=p_t[0],
            b3_truth=p_t[1] - p_t[0], b5p_truth=p_t[2] - ratio(tv[0] + tv[1], tn[0] + tn[1]),
        )
        assert tuple(out) == VIGIL_STAT_COLUMNS
        return out

    def _window_accumulate(self, e_prev: np.ndarray) -> None:
        """v2.2r 창 지표를 센다. `step` 이 `_accumulate` 뒤, 관측(8)으로 `self._g` 를 바꾸기 전에 부른다.

        구간은 결정 때 상태다: 보임 = 결정 관측의 포식자 수 > 0, 창 = `self.window`(`step` 0, 동역학과 같은 theta),
        평시 = 그 밖. 배부름 = 결정 때 energy ≥ HUNGRY·max_energy. 정지 = 이번 스텝의 실제 보행 정지(경계 포함).
        """
        g = self._g
        seg = np.where(g["pred_count"] > 0, 2, self.window.astype(np.int64))   # 0 평시, 1 창 안, 2 보임
        full = e_prev >= HUNGRY * self.cfg.max_energy
        stop = (self.gait == GAIT_STOP) if self._sp is not None else self.vigilant
        code = ((seg * 2 + full) * 2 + stop) * 2 + self.vigilant   # WINDOW_HIST_SHAPE 의 C 순서 평탄 인덱스
        self._win_hist += np.bincount(code, minlength=self._win_hist.size).reshape(WINDOW_HIST_SHAPE)
        self._win_look += int(np.count_nonzero(self.looked))

    def window_stats(self) -> dict:
        """v2.2r 창 지표 — reset 뒤 누적 (수정 제안서 3.8 선택 규칙 (i)·B3 정의). 열 순서는 `WINDOW_STAT_COLUMNS`.

        비율은 개체-스텝 기준이고 분모가 0 이면 nan 이다. 창은 동역학의 theta 로 정한다.
        - win_frac: 결정 때 창 안 비율
        - p_stop_win·p_stop_calm: 창 안·평시의 P(실제 정지). *_full·*_hungry 는 결정 때 energy ≥ 0.5 / < 0.5 표본만
        - b3_l = p_stop_win_full − p_stop_calm_full — L 의 새 결정 사용 지표(B3_L). 배고파서 멈춘 경우를 떼려고
          배부른 표본만 쓴다. 상수 정책도 창 안·평시의 상태 분포 차이로 0 이 아닐 수 있다(대조군과 비교한다)
        - p_vig_win·p_vig_win_full·p_vig_win_hungry·p_vig_calm_w: 경계(효력이 난 경계) 비율. W′ 의 사용 지표는
          p_vig_win 이고, window_only 면 p_vig_calm_w 는 구성상 0 이다. action false 세계는 모두 0 이다.
          (평시 열 이름에 _w 를 붙인 것은 vigil_stats 의 p_vig_calm 과 rollout 행에서 겹치지 않게 하려는 것이다)
        - look_frac·look_win_frac: 반사 돌아보기가 돈 개체-스텝 비율(전체 대비, 창 안 대비). look_back 을 끄면 0
        """
        nan = float("nan")
        H = self._win_hist                                      # [구간, 배부름, 정지, 경계]
        n = int(H.sum())

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        sf = H.sum(3)                                           # [구간, 배부름, 정지]
        nf = sf.sum(2)                                          # [구간, 배부름]
        vf = H[..., 1].sum(2)                                   # [구간, 배부름] 경계 수

        def p_stop(k):
            return ratio(sf[k, :, 1].sum(), nf[k].sum())

        def p_stop_f(k, f):
            return ratio(sf[k, f, 1], nf[k, f])

        out = dict(
            win_frac=ratio(nf[1].sum(), n),
            p_stop_win=p_stop(1), p_stop_calm=p_stop(0),
            p_stop_win_full=p_stop_f(1, 1), p_stop_calm_full=p_stop_f(0, 1),
            b3_l=p_stop_f(1, 1) - p_stop_f(0, 1),
            p_stop_win_hungry=p_stop_f(1, 0), p_stop_calm_hungry=p_stop_f(0, 0),
            p_vig_win=ratio(vf[1].sum(), nf[1].sum()), p_vig_win_full=ratio(vf[1, 1], nf[1, 1]),
            p_vig_win_hungry=ratio(vf[1, 0], nf[1, 0]), p_vig_calm_w=ratio(vf[0].sum(), nf[0].sum()),
            look_frac=ratio(self._win_look, n), look_win_frac=ratio(self._win_look, nf[1].sum()),
        )
        assert tuple(out) == WINDOW_STAT_COLUMNS
        return out

    def _daynight_accumulate(self, e_prev, caught, starved, intake, drain) -> None:
        """v2.4 위상 지표를 센다. `step` 이 다른 누적 뒤, `_daynight_update`·관측(8) 전에 부른다.

        위상 구간은 이번 스텝 동역학이 쓴 결정 때 어둠 `self.dark` 다. 배부름·은신처 안·포식자 거리는 결정 때 상태
        (`e_prev`, 스텝 전 기하 `self._g`), 보행은 이번 스텝의 실제 보행(B1·B2 는 gait_stats 처럼 명령 보행), 먹이 셀은
        이번 스텝의 섭식 위치(이동 뒤 `self.pos`) 셀의 cap0 > 0 이다. 사망·섭취·대사는 이번 스텝 값이다.
        """
        cfg, g = self.cfg, self._g
        d = self.dark
        ph = 0 if d <= DN_EDGES[0] + DN_TOL else (2 if d >= DN_EDGES[1] - DN_TOL else 1)
        full = e_prev >= HUNGRY * cfg.max_energy
        vig = self.vigilant if self._vg is not None else np.zeros(self.N, dtype=bool)
        ix, iy = self._cell_index(self.pos)
        food_cell = self.food_cap[iy, ix] > 0.0
        code = ((((ph * 2 + full) * 2 + g["in_cover"]) * 3 + self.gait) * 2 + vig) * 2 + food_cell
        self._dn_hist += np.bincount(code, minlength=self._dn_hist.size).reshape(DN_HIST_SHAPE)
        if self._rp is not None:        # v3: 휴식·먹기 열의 행동 기준 판 (daynight_stats)
            code = (((ph * 2 + full) * 2 + g["in_cover"]) * 2 + food_cell) * rep.N_BEHAVIORS + self._rs.behavior
            self._dn_rep += np.bincount(code, minlength=self._dn_rep.size).reshape(self._dn_rep.shape)
        dd = g["d_pred_min"] / cfg.see_r
        b = (dd < np.inf) * (1 + (dd >= B1_EDGES[0]) + (dd >= B1_EDGES[1]))
        code = (((vig * 3 + ph) * 3 + self.gait_cmd) * 4 + b) * 2 + full
        self._dn_b += np.bincount(code, minlength=self._dn_b.size).reshape(DN_B_SHAPE)
        self._dn_dead[0, ph] += int(np.count_nonzero(caught))
        self._dn_dead[1, ph] += int(np.count_nonzero(starved))
        self._dn_energy[0, ph] += float(intake.sum())
        self._dn_energy[1, ph] += float(drain.sum())
        self._dn_dark += d
        self._dn_steps += 1

    def daynight_stats(self) -> dict:
        """v2.4 위상 지표 — reset 뒤 누적 (계획서 6.2 N1·N5′·N2, 2-5 행 Gate N). 열 순서는 `DAYNIGHT_STAT_COLUMNS`.

        위상 = 결정 때 어둠 d 의 구간(낮 d ≤ 0.2, 박명, 밤 d ≥ 0.8). 비율은 개체-스텝 기준이고 분모가 0 이면 nan 이다
        (낮 고정 세계는 밤 열이 nan 이다).
        - dn_period·dn_offset·dn_day_fixed·dn_induced: 이 세계의 T, 시작 위상, 낮 고정 여부, 시작 상태 유도 여부
        - dark_mean: 스텝 평균 d. frac_day·frac_twi·frac_night: 위상 구간 개체-스텝 비율
        - pred_rate_*·starve_rate_*: 위상 구간의 피식·아사 / 개체-스텝 (Gate N (a1)·(a3))
        - intake_*·drain_*: 개체-스텝당 먹이 에너지·대사. intake_ratio_nd = intake_night / intake_day (Gate N (a2))
        - p_rest_cover_*: P(결정 때 은신처 안 & 실제 정지 & 비경계). n1 = 밤 − 낮 (N1, 1차). 실제 보행이라 방향이 없어
          멈춘 개체(stall)도 든다 — 상수 정책에서도 정확히 0 은 아니다(C2 최대 +0.002, 10-06 검토)
        - p_eat_*_{hungry,full}: P(먹이 셀 & 실제 정지·걷기 & 비경계 | 위상, 결정 때 energy < 0.5 / ≥ 0.5).
          n5p = p_eat_night_hungry − p_eat_night_full (N5′ 원값). 상태 분포 효과로 상수 정책에서도 크게 음수라(배고픈 개체는
          먹이 밖에 있다) 1차 정의는 C1′(행동 순열) 대비 차다(results/v2/v2_4/PREREG.md 0절)
        - p_stop_*·p_run_*·p_cover_*: 실제 정지·뛰기·결정 때 은신처 안 비율. p_stop_night_{hungry,full}: 밤의 배고픔별 정지
        - b1_*·b2_*: gait_stats 의 B1·B2 를 위상 구간 안에서 잰 값(명령 보행, 경계 개체는 뛰지 않음·정지에서 뺀다)
        - n2: P(경계 | 밤, 안 보임) − P(경계 | 낮, 안 보임) (2차). vigilance 를 끈 세계는 nan
        repertoire(v3)를 켠 세계는 보행이 행동을 뜻하지 않으므로(FREEZE·HIDE·SLEEP 도 정지, 은신처 안 GRAZE 정지는 먹기다)
        휴식·먹기 열을 행동 기준으로 센다: p_rest_cover_*·n1 = P(결정 때 은신처 안 & SLEEP), p_eat_*·n5p = P(먹이 셀 & GRAZE).
        나머지 열(정지·뛰기·은신처 비율, B1·B2)은 실제 보행 그대로다.
        """
        nan = float("nan")
        H = self._dn_hist                                       # [위상, 배부름, 은신처, 보행, 경계, 먹이 셀]

        def ratio(x, y):
            return float(x) / float(y) if y else nan

        n_ph = H.reshape(3, -1).sum(1)
        n_all = int(n_ph.sum())
        if self._rp is None:
            rest_cover = H[:, :, 1, GAIT_STOP, 0, :].sum((1, 2))
            eat = H[:, :, :, :2, 0, 1].sum((2, 3))              # [위상, 배부름] 먹이 셀 & 정지·걷기 & 비경계
        else:                                                   # [위상, 배부름, 은신처, 먹이 셀, 행동]
            rest_cover = self._dn_rep[:, :, 1, :, rep.SLEEP].sum((1, 2))
            eat = self._dn_rep[:, :, :, 1, rep.GRAZE].sum(2)
        n_pf = H.sum((2, 3, 4, 5))                               # [위상, 배부름]
        gait_ph = H.sum((1, 2, 4, 5))                            # [위상, 보행]
        cover_ph = H[:, :, 1].sum((1, 2, 3, 4))
        stop_pf = H[:, :, :, GAIT_STOP].sum((2, 3, 4))           # [위상, 배부름]

        B = self._dn_b                                          # [경계, 위상, 명령, 거리 구간, 배부름]
        Ball = B.sum(0)
        B0 = B[0]

        def b1(ph):
            near = Ball[ph, :, 1:3].sum((1, 2))                 # [명령] 보임 & d < 0.5
            un = Ball[ph, :, 0].sum(1)
            near_run = B0[ph, GAIT_RUN, 1:3].sum()
            un_run = B0[ph, GAIT_RUN, 0].sum()
            return ratio(near_run, near.sum()) - ratio(un_run, un.sum())

        def b2(ph):
            st = B0[ph, GAIT_STOP].sum(0)                        # [배부름] 경계 아닌 명령 정지
            nn = Ball[ph].sum((0, 1))
            return ratio(st[0], nn[0]) - ratio(st[1], nn[1])

        if self._vg is not None:
            unseen = Ball.sum(1)[:, 0].sum(1)                   # [위상] 안 보임 개체-스텝
            vig_un = B[1].sum(1)[:, 0].sum(1)
            n2 = ratio(vig_un[2], unseen[2]) - ratio(vig_un[0], unseen[0])
        else:
            n2 = nan
        e_day, e_twi, e_night = (self._dn_energy[0, k] for k in range(3))
        out = dict(
            dn_period=float(self.dn_period), dn_offset=float(self.dn_offset),
            dn_day_fixed=float(self.day_fixed), dn_induced=float(self.dn_induced),
            dark_mean=ratio(self._dn_dark, self._dn_steps),
            frac_day=ratio(n_ph[0], n_all), frac_twi=ratio(n_ph[1], n_all), frac_night=ratio(n_ph[2], n_all),
            pred_rate_day=ratio(self._dn_dead[0, 0], n_ph[0]), pred_rate_twi=ratio(self._dn_dead[0, 1], n_ph[1]),
            pred_rate_night=ratio(self._dn_dead[0, 2], n_ph[2]),
            starve_rate_day=ratio(self._dn_dead[1, 0], n_ph[0]), starve_rate_twi=ratio(self._dn_dead[1, 1], n_ph[1]),
            starve_rate_night=ratio(self._dn_dead[1, 2], n_ph[2]),
            intake_day=ratio(e_day, n_ph[0]), intake_twi=ratio(e_twi, n_ph[1]), intake_night=ratio(e_night, n_ph[2]),
            intake_ratio_nd=ratio(ratio(e_night, n_ph[2]), ratio(e_day, n_ph[0])) if n_ph[0] and n_ph[2] else nan,
            drain_day=ratio(self._dn_energy[1, 0], n_ph[0]), drain_night=ratio(self._dn_energy[1, 2], n_ph[2]),
            p_rest_cover_day=ratio(rest_cover[0], n_ph[0]), p_rest_cover_night=ratio(rest_cover[2], n_ph[2]),
            n1=ratio(rest_cover[2], n_ph[2]) - ratio(rest_cover[0], n_ph[0]),
            p_eat_night_hungry=ratio(eat[2, 0], n_pf[2, 0]), p_eat_night_full=ratio(eat[2, 1], n_pf[2, 1]),
            n5p=ratio(eat[2, 0], n_pf[2, 0]) - ratio(eat[2, 1], n_pf[2, 1]),
            p_eat_day_hungry=ratio(eat[0, 0], n_pf[0, 0]), p_eat_day_full=ratio(eat[0, 1], n_pf[0, 1]),
            p_stop_day=ratio(gait_ph[0, GAIT_STOP], n_ph[0]), p_stop_night=ratio(gait_ph[2, GAIT_STOP], n_ph[2]),
            p_run_day=ratio(gait_ph[0, GAIT_RUN], n_ph[0]), p_run_night=ratio(gait_ph[2, GAIT_RUN], n_ph[2]),
            p_cover_day=ratio(cover_ph[0], n_ph[0]), p_cover_night=ratio(cover_ph[2], n_ph[2]),
            p_stop_night_hungry=ratio(stop_pf[2, 0], n_pf[2, 0]), p_stop_night_full=ratio(stop_pf[2, 1], n_pf[2, 1]),
            b1_day=b1(0), b1_night=b1(2), b2_day=b2(0), b2_night=b2(2), n2=n2,
        )
        assert tuple(out) == DAYNIGHT_STAT_COLUMNS
        return out

    def pred_sleep_stats(self) -> dict:
        """v2.4s 포식자 잠 통계 — reset 뒤 누적. 열 순서는 `PSLEEP_STAT_COLUMNS`.
        pred_noct_frac: 이 세계의 야행성 비율 q, pred_noct_n: 야행성 포식자 수, pred_asleep_mean: 스텝 평균 자는 포식자 비율."""
        # v1 포식자만 센다(threats 의 플레이어 칸은 밤잠 배열에 야행성으로 들어 있다. 끈 세계는 M_base = M)
        out = dict(pred_noct_frac=float(self.pred_noct_frac),
                   pred_noct_n=float(self.pred_nocturnal[:self.M_base].sum()),
                   pred_asleep_mean=self._ps_asleep_sum / self._ps_steps if self._ps_steps else float("nan"))
        assert tuple(out) == PSLEEP_STAT_COLUMNS
        return out

    def _rep_accumulate(self, out: dict, caught: np.ndarray, starved: np.ndarray) -> None:
        """v3 레퍼토리 지표를 센다. `step` 이 `_accumulate` 바로 뒤, 시간을 넘기기(tick)·어둠 갱신·관측 전에 부른다.

        위상 구간은 결정 때 어둠(daynight_stats 와 같은 DN_EDGES), 위협 보임은 결정 관측의 포식자 수 > 0, 행동은 이번 스텝에
        실행한 행동이다. 깜빡임 = 행동이 A → B 로 바뀐 뒤 FLICKER_SECONDS(3초 = 22스텝) 안에 B → A 로 되돌아온 전환.
        """
        d = self.dark
        ph = 0 if d <= DN_EDGES[0] + DN_TOL else (2 if d >= DN_EDGES[1] - DN_TOL else 1)
        b = self._rs.behavior.astype(np.int64)
        seen = (self._g["pred_count"] > 0).astype(np.int64)
        K = rep.N_BEHAVIORS
        self._rep_hist[ph] += np.bincount(seen * K + b, minlength=2 * K).reshape(2, K)
        self._rep_dead[0] += np.bincount(b[caught], minlength=K)
        self._rep_dead[1] += np.bincount(b[starved], minlength=K)
        sw = out["switch"]
        self._rep_decide += int(np.count_nonzero(out["decide"]))
        if sw.any():
            i = np.flatnonzero(sw)
            self._rep_switch += len(i)
            t = self.t
            flick = (b[i] == self._rep_before[i]) & (t - self._rep_last_sw[i] <= self._rep_flicker_w)
            self._rep_flicker += int(np.count_nonzero(flick))
            self._rep_sw_slot[i] += 1
            self._rep_flick_slot[i[flick]] += 1
            self._rep_before[i] = out["prev"][i]
            self._rep_last_sw[i] = t

    def rep_slot_counts(self) -> dict:
        """슬롯별 행동 전환 수·깜빡임 수 (N,) int64 사본 — reset 뒤 누적, 같은 슬롯의 개체들을 합친다(repertoire_stats 의
        switch·flicker 와 같은 정의라 합이 같다). 침입 시험이 침입·거주로 나눠 쓴다."""
        if self._rp is None:
            raise ValueError("rep_slot_counts 는 repertoire 를 켠 세계에만 있다")
        return dict(switch=self._rep_sw_slot.copy(), flicker=self._rep_flick_slot.copy())

    def repertoire_stats(self) -> dict:
        """v3 레퍼토리 통계 — reset 뒤 누적. 열 순서는 `REP_STAT_COLUMNS`. 비율은 개체-스텝 기준, 분모가 0 이면 nan.

        - use_<행동>: 행동 사용 비율. use_day_·use_night_: 낮(d ≤ 0.2)·밤(d ≥ 0.8) 구간 안의 비율,
          use_seen_·use_unseen_: 결정 때 위협이 보인·안 보인 개체-스텝 안의 비율
        - pred_rate_<행동>·starve_rate_<행동>: 그 행동 중에 죽은 수(피식·아사) / 그 행동의 개체-스텝
        - seen_frac: 결정 때 위협이 보인 비율, switch_per_sec: 개체당 초당 행동 전환 수, flicker_rate: 전환 중 3초 안 A-B-A
          되돌림 비율, decide_frac: 결정 시점(잠금 끝 또는 사건 결정)인 개체-스텝 비율
        """
        if self._rp is None:
            raise ValueError("repertoire_stats 는 repertoire 를 켠 세계에만 있다")
        H = self._rep_hist                                      # [위상, 보임, 행동]
        n = int(H.sum())

        def ratio(x, y):
            return float(x) / float(y) if y else float("nan")

        tot, day, night = H.sum((0, 1)), H[0].sum(0), H[2].sum(0)
        seen, unseen = H[:, 1].sum(0), H[:, 0].sum(0)
        out = {}
        for pre, arr in (("use_", tot), ("use_day_", day), ("use_night_", night), ("use_seen_", seen),
                         ("use_unseen_", unseen)):
            for k, name in enumerate(rep.BEHAVIOR_NAMES):
                out[pre + name] = ratio(arr[k], arr.sum())
        for pre, row in (("pred_rate_", 0), ("starve_rate_", 1)):
            for k, name in enumerate(rep.BEHAVIOR_NAMES):
                out[pre + name] = ratio(self._rep_dead[row, k], tot[k])
        per_sec = 60.0 / float(self.cfg.policy_interval)
        out.update(seen_frac=ratio(seen.sum(), n), switch_per_sec=ratio(self._rep_switch, n) * per_sec,
                   flicker_rate=ratio(self._rep_flicker, self._rep_switch), decide_frac=ratio(self._rep_decide, n))
        assert tuple(out) == REP_STAT_COLUMNS
        return out

    def threats_stats(self) -> dict:
        """v3 위협 통계 — reset 뒤 누적. 열 순서는 `THREAT_STAT_COLUMNS`.
        p_stalk: 이 세계의 잠행형 비율(뽑은 값), stalker_n: 잠행형 수, player_present: 플레이어 유무(0/1),
        catch_rate_*: 유형별 포획 수 / 개체-스텝(근접 추격·원거리 추격·잠행·플레이어), pounce_n: 돌진 시작 수,
        pounce_hit: 돌진 중 포획 / 돌진 시작(없으면 nan), player_charge_n: 플레이어 돌진 시작 수."""
        if self._th is None:
            raise ValueError("threats_stats 는 threats 를 켠 세계에만 있다")
        n = max(self.t * self.N, 1)
        c, p = self._th_catch, self._th_pounce
        out = dict(p_stalk=float(self.threat_p_stalk), stalker_n=float(np.count_nonzero(self.pred_type == PT_STALKER)),
                   player_present=float(self.player_present),
                   catch_rate_chaser=c[0] / n, catch_rate_ranged=c[1] / n, catch_rate_stalker=c[2] / n,
                   catch_rate_player=c[3] / n, pounce_n=float(p[0]),
                   pounce_hit=float(p[1]) / float(p[0]) if p[0] else float("nan"),
                   player_charge_n=float(self._th_charge))
        assert tuple(out) == THREAT_STAT_COLUMNS
        return out

    def stare_stats(self) -> dict:
        """v3 R2 M7 통계 — reset 뒤 누적. 열 순서는 `STARE_STAT_COLUMNS`(명세 2-6). 분모가 0 이면 nan.
        standoff_n: 대치 시작 수, standoff_break_n: 물러남 없이 끝난 대치(노려보기가 풀림·잠금을 잃음) 수, blink_catch_n: 깨진
        대치 뒤 BLINK_STEPS 안에 그 표적이 잡힌 수, balk_n: 물러남 수, balk_share = 물러남 / (물러남 + 잠행형 돌진 시작),
        spotted_n: 플레이어가 새로 들킨 수(들킴 중 다시 spot_steps 를 채워 남은 스텝이 갱신된 것은 세지 않는다),
        spotted_charge_n·spotted_charge_catch_n: 들킨 돌진 수와 그 포획 수(옆 개체 포획 포함), lock_steps_mean: 잠금
        위협-스텝 / 잠금 시작 수(새 잠금은 숨은 개체에도 걸 수 있어 다음 C0 이 지우면 다시 센다 — `_stare_target`),
        stare_frac: 노려보는(나를 잠근 위협이 S 를 세는 중인) 개체-스텝 비율, standoff_break_beh_n: 깨진 대치 중 그때 잠긴 표적이
        FREEZE 가 아닌 수(표적이 행동을 바꿔 깸), spotted_charge_catch_frac = spotted_charge_catch_n / spotted_charge_n,
        unspotted_charge_catch_frac = 들키지 않은 플레이어 돌진 중 포획 / (플레이어 돌진 − 들킨 돌진)."""
        if self._sd is None:
            raise ValueError("stare_stats 는 stare_down 을 켠 세계에만 있다")
        n = max(self.t * self.N, 1)
        pn = int(self._th_pounce[0])

        def ratio(x, y):
            return float(x) / float(y) if y else float("nan")
        out = dict(standoff_n=float(self._sd_standoff_n), standoff_break_n=float(self._sd_break_n),
                   blink_catch_n=float(self._sd_blink_n), balk_n=float(self._sd_balk_n),
                   balk_share=ratio(self._sd_balk_n, self._sd_balk_n + pn), spotted_n=float(self._sd_spotted_n),
                   spotted_charge_n=float(self._sd_spotted_charge_n),
                   spotted_charge_catch_n=float(self._sd_spotted_charge_catch_n),
                   lock_steps_mean=ratio(self._sd_lock_steps, self._sd_lock_n), stare_frac=self._sd_stare_steps / n,
                   standoff_break_beh_n=float(self._sd_break_beh_n),
                   spotted_charge_catch_frac=ratio(self._sd_spotted_charge_catch_n, self._sd_spotted_charge_n),
                   unspotted_charge_catch_frac=ratio(self._sd_charge_catch_n, self._th_charge - self._sd_spotted_charge_n))
        assert tuple(out) == STARE_STAT_COLUMNS
        return out

    def alarm_stats(self) -> dict:
        """v3 R2 M8 통계 — reset 뒤 누적. 열 순서와 뜻은 `ALARM_STAT_COLUMNS` 주석(명세 3-7, 사전 등록 5절). 분모가 0 이면 nan.
        alarm_r 0 이고 on_catch false 인 중립 세계는 블록을 건너뛰므로 수는 0 이고 비율은 nan 이다."""
        if self._al is None:
            raise ValueError("alarm_stats 는 alarm 을 켠 세계에만 있다")
        n = max(self.t * self.N, 1)

        def ratio(x, y):
            return float(x) / float(y) if y else float("nan")
        e, eh = self._al_entry, self._al_entry_heard
        out = dict(emit_h0=float(self._al_emit_n[0]), emit_h1=float(self._al_emit_n[1]), emit_h2=float(self._al_emit_n[2]),
                   cry_n=float(self._al_cry), listen_per_emit=ratio(self._al_listen, self._al_emitters),
                   alarm_frac=self._al_with / n, alarm_unseen_frac=ratio(self._al_with_unseen, self._al_with),
                   e7_n=float(self._al_e7_n), e7_switch_frac=ratio(self._al_e7_sw, self._al_e7_n),
                   heard_entry_flee=ratio(eh[rep.FLEE], e[rep.FLEE]), heard_entry_hide=ratio(eh[rep.HIDE], e[rep.HIDE]),
                   heard_entry_freeze=ratio(eh[rep.FREEZE], e[rep.FREEZE]),
                   alarm_gap_mean=ratio(self._al_gap_sum, self._al_gap_n), dir_n=float(self._al_dir_n),
                   dir_ok_pt=ratio(self._al_dir_pt, self._al_dir_n), dir_ok_copy=ratio(self._al_dir_cp, self._al_dir_n),
                   wave_size_mean=ratio(self._al_wave_hits, self._al_h0),
                   heads_up_1s=ratio(self._al_heads_up, self._al_heads_n),
                   false_alarm_frac=ratio(self._al_false, self._al_seen0),
                   e7_decide_frac=ratio(self._al_e7_dn, self._al_e7_n),
                   heads_up_1s_r16=ratio(self._al_heads16_up, self._al_heads16_n))
        assert tuple(out) == ALARM_STAT_COLUMNS
        return out

    def realism_stats(self) -> dict:
        """v3 현실성 1단계 통계 — reset 뒤 누적. 열 순서와 뜻은 `REALISM_STAT_COLUMNS` 주석. 켜지 않은 규칙의 열과 분모가 0 인
        비율은 nan 이다."""
        if not self._rz:
            raise ValueError("realism_stats 는 realism_* 중 하나라도 켠 세계에만 있다")
        nan = float("nan")

        def ratio(x, y):
            return float(x) / float(y) if y else nan
        vision, hear, shel, food, night = (x is not None for x in (self._zv, self._zh, self._zs, self._zf, self._zn))
        out = dict(rear_seen_frac=ratio(self._rz_rear_n, self._rz_obs_n) if vision else nan,
                   heard_only_frac=ratio(self._rz_heard_n, self._rz_obs_n) if hear else nan,
                   safe_frac=ratio(self._zs_safe_n, self._zs_steps) if shel else nan,
                   safe_saved_n=float(self._zs_saved_n) if shel else nan,
                   food_cap_kept=float(self._zf_kept) if food else nan,
                   cover_intake_share=ratio(self._zf_in, self._zf_all) if food else nan,
                   dark_awake_frac=ratio(self._zn_dark_awake, self._zn_dark_n) if night else nan,
                   settle_n=float(self._zn_settle_n) if night else nan,
                   settle_abort_n=float(self._zn_abort_n) if night else nan,
                   onset_n=float(self._zn_onset_n) if night else nan,
                   block_deer_n=float(self._zn_block_deer_n) if night else nan,
                   block_hunt_n=float(self._zn_block_hunt_n) if night else nan,
                   wake_n=float(self._zn_wake_n) if night else nan)
        assert tuple(out) == REALISM_STAT_COLUMNS
        return out

    def r3_stats(self) -> dict:
        """v3 R3 세계 통계 — reset 뒤 누적(세계 값은 마지막 reset 세계). 열 순서와 뜻은 `R3_STAT_COLUMNS` 주석. 켜지 않은 규칙의 열과
        분모가 0 인 비율은 nan 이다."""
        if not self._r3:
            raise ValueError("r3_stats 는 R3 규칙(realism_chase·realism_terrain·realism_shelter.block_predators·"
                             "realism_cover_food.frac_range) 중 하나라도 켠 세계에만 있다")
        nan = float("nan")
        chase, terr, wall, food = self._zc is not None, self._zt is not None, self._zw, self._zf is not None
        out = {}
        for key, attr in (("chase_lock_n", "_zc_lock_n"), ("chase_held_n", "_zc_held"), ("chase_lost_n", "_zc_lost"),
                          ("chase_rel_cover_n", "_zc_rel_cover"), ("chase_rel_lost_n", "_zc_rel_lost"),
                          ("chase_rel_state_n", "_zc_rel_state"), ("chase_rel_catch_n", "_zc_rel_catch"),
                          ("chase_catch_own_n", "_zc_catch_own"), ("chase_rel_dead_n", "_zc_rel_dead")):
            out[key] = float(getattr(self, attr)) if chase else nan
        for key, attr in (("wall_push_n", "_zw_push_n"), ("wall_slide_n", "_zw_slide_n"), ("wall_stuck_n", "_zw_stuck_n"),
                          ("wall_giveup_n", "_zw_giveup_n"), ("wall_inside_n", "_zw_inside_n"),
                          ("wall_reset_n", "_zw_reset_moved")):
            out[key] = float(getattr(self, attr)) if wall else nan
        out["cover_food_cap"] = float(self.cover_food_cap) if food else nan
        out["cover_food_regen"] = float(self.cover_food_regen) if food else nan
        for key in ("snow_target", "rough_target", "snow_frac_actual", "rough_frac_actual"):
            out[key] = float(getattr(self, key)) if terr else nan
        if terr:
            kinds = self.terrain_patches[:, 0]
            out["snow_patches"] = float(np.count_nonzero(kinds == TERRAIN_SNOW))
            out["rough_patches"] = float(np.count_nonzero(kinds == TERRAIN_ROUGH))
        else:
            out["snow_patches"] = out["rough_patches"] = nan
        for i, t in enumerate(TERRAIN_NAMES):
            out[f"deer_n_{t}"] = float(self._zt_deer[i]) if terr else nan
        for i, t in enumerate(TERRAIN_NAMES):
            out[f"catch_{t}_n"] = float(self._zt_catch[i]) if terr else nan
        for i, t in enumerate(TERRAIN_NAMES):
            out[f"catch_rate_{t}"] = (float(self._zt_catch[i]) / float(self._zt_deer[i]) if terr and self._zt_deer[i]
                                      else nan)
        for i, t in enumerate(TERRAIN_NAMES):
            out[f"pounce_{t}_n"] = float(self._zt_pounce[i]) if terr else nan
        for i, t in enumerate(TERRAIN_NAMES):
            out[f"pounce_hit_{t}_n"] = float(self._zt_pounce_hit[i]) if terr else nan
        assert tuple(out) == R3_STAT_COLUMNS
        return out

    def stats(self) -> dict:
        """§7.2 반환 열."""
        n, steps = self.N, max(self.t, 1)
        agent_steps = max(self._agent_steps, 1)
        lives = self._life_sum + int(self._life_cur.sum())
        n_lives = self._life_count + n
        flee_mean = self._act_sum[2] / agent_steps
        flee_var = max(self._flee_sq / agent_steps - flee_mean**2, 0.0)

        def _d(sum_a, n_a, sum_b, n_b):
            if n_a == 0 or n_b == 0:
                return float("nan")
            return float(np.abs(sum_a / n_a - sum_b / n_b).mean())

        if self._rp is not None:
            # repertoire(v3) 세계는 v1 조향 행동 열이 없어 cohesion_mean·flee_dist_mean·flee_dist_std·react_pred·react_hunger 가
            # nan 이다(0 이 실측처럼 보이지 않게. 행동 분포는 repertoire_stats). 열 순서는 v1 과 같다
            nan = float("nan")
            return dict(mean_return=self._rew_total / n, survival=lives / max(n_lives, 1),
                        repro=self._repro_total / n, predation_rate=self._pred_deaths / (steps * n),
                        cohesion_mean=nan, flee_dist_mean=nan, flee_dist_std=nan,
                        cover_frac=self._cover_steps / agent_steps, react_pred=nan, react_hunger=nan)
        return dict(
            mean_return=self._rew_total / n,
            survival=lives / max(n_lives, 1),
            repro=self._repro_total / n,
            predation_rate=self._pred_deaths / (steps * n),
            cohesion_mean=self._act_sum[1] / agent_steps,
            flee_dist_mean=flee_mean,
            flee_dist_std=float(np.sqrt(flee_var)),
            cover_frac=self._cover_steps / agent_steps,
            react_pred=_d(self._a_pred, self._n_pred, self._a_nopred, self._n_nopred),
            react_hunger=_d(
                np.array([self._f_hungry]),
                self._n_hungry,
                np.array([self._f_full]),
                self._n_full,
            ),
        )

    def food_stats(self) -> dict:
        """v2.0b 먹이 통계 — 지금 시점의 값 (v1 `stats()` 10열 밖, 계획서 4.8). Gate F·영상·기록 학습이 쓴다.

        지역은 v2.3 전까지 맵 좌우 절반(`_left_half`)으로 대신한다. 모두 cap0 > 0 셀만 센다.
        접미사 없음 = 맵 전체, `_left`·`_right` = 절반.
        - v_ratio, f_ratio: 지역 비율 ΣV/Σcap0, ΣF/Σcap0 (v2.3 지역 장부의 V_r·F_r 정의, 4.4)
        - v_cell_mean: 셀별 V/cap0 의 평균 (Gate F (a) "평균 V/cap0")
        - floor_frac: V/cap0 ≤ floor + FOOD_V_FLOOR_TOL 인 셀 비율 (Gate F (a) "하한에 붙은 셀")
        - eaten: reset 뒤 누적 섭취량의 합
        - half_life, rho, init_left, init_right: 이 세계에서 뽑은 회복 반감기와 V 초기 비율
        food_v 를 끈 세계는 V = cap0 로 본다(v_ratio 1). 하한·기록·뽑은 값이 없는 열은 nan 이다.
        절반에 cap0 > 0 셀이 없으면 그 절반의 열은 nan 이다.
        """
        on = self._fv is not None
        nan = float("nan")
        cap0, F = self.food_cap, self.food
        V = self.food_v if on else cap0
        pos = cap0 > 0.0
        left = self._left_half()
        out = dict(
            half_life=float(self.food_v_half_life) if on else nan,
            rho=float(self.food_v_rho) if on else nan,
            init_left=self.food_v_init[0] if on else nan,
            init_right=self.food_v_init[1] if on else nan,
        )
        tol = self._fv["floor"] + FOOD_V_FLOOR_TOL if on else nan
        for sfx, m in (("", pos), ("_left", pos & left), ("_right", pos & ~left)):
            c = cap0[m]
            s = float(c.sum())
            if s <= 0.0:
                for key in ("v_ratio", "f_ratio", "v_cell_mean", "floor_frac", "eaten"):
                    out[key + sfx] = nan
                continue
            vr = V[m] / c
            out["v_ratio" + sfx] = float(V[m].sum()) / s
            out["f_ratio" + sfx] = float(F[m].sum()) / s
            out["v_cell_mean" + sfx] = float(vr.mean())
            out["floor_frac" + sfx] = float((vr <= tol).mean()) if on else nan
            out["eaten" + sfx] = float(self._fv_eaten[m].sum()) if on else nan
        return out

    def food_cells(self) -> dict:
        """셀별 먹이 상태의 사본, 모두 (gw, gw) 이고 [iy, ix] 순서. Gate F (b) V 자기상관, (c) 흔적 진폭
        (누적 섭취 상위 10% 셀 vs 같은 cap0 구간 하위 50%, 섭식이 멈춘 뒤 경과), 영상의 짓밟힌 땅이 쓴다.

        - food_cap(cap0), food(F), food_v(V), left(왼쪽 절반), cover(은신처 셀)
        - eaten: reset 뒤 누적 섭취량, last_eat: 마지막으로 뜯긴 스텝의 self.t (뜯긴 적 없으면 −1)
        food_v 를 끈 세계는 food_v = cap0 사본이고 eaten·last_eat 는 None 이다.
        """
        on = self._fv is not None
        return dict(
            food_cap=self.food_cap.copy(),
            food=self.food.copy(),
            food_v=(self.food_v if on else self.food_cap).copy(),
            left=self._left_half(),
            cover=self.cover_cell.copy(),
            eaten=self._fv_eaten.copy() if on else None,
            last_eat=self._fv_last_eat.copy() if on else None,
        )
