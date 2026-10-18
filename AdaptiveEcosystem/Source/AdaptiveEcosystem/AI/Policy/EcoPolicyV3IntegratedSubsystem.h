// 팀 통합 레벨을 v3 R1b 두뇌로 돌리는 서비스 — "몸은 팀 것, 머리만 우리 것" (계획서 RL_V3_UNREAL_TRAINING_PLAN.md 4-5b).
//
// 스위치 (기본 끔. 끄면 아무것도 바꾸지 않는다 — 팀 레벨은 지금처럼 v1 + Social + 팀 늑대로 돈다):
//   편집기 콘솔에서 Play 전에  eco.IntegratedPolicyVersion 3     (1 = 끔, 기본)
//   명령줄                     -EcoIntegratedV3                   (헤드리스·독립형 게임 실행용)
//   명령줄 값은 콘솔 변수의 시작값(ECVF_SetByCommandline)으로만 들어간다. 그래서 콘솔에서 eco.IntegratedPolicyVersion 1 을 넣으면
//   명령줄이 있어도 꺼진다(-EcoV3Debug·-EcoV3Seed=·-EcoV3DeerPerRegion= 도 같다).
//   통합된 권위 경로는 Standalone / Listen / Dedicated Server 에서 실행한다. Client 는 같은 경로/GUID의 canonical
//   transient EntityConfig만 등록하고 논리 스텝은 실행하지 않는다. Bubble DTO로 표현만 수신한다.
//   편집기 콘솔 값은 별도 Standalone 프로세스로 전달되지 않으므로 추가 실행 인수에 -EcoIntegratedV3 를 넣는다.
//
// 맡는 것 (서버·단독만, AGENTS.md 2절 2항. 복제 통로가 아니다 — 2절 6항):
//   1. OnWorldBeginPlay (액터 BeginPlay 앞, UE 5.8 UWorld::BeginPlay): 팀 조정자 AEcoCreatureIntegrationSpawner 의 공개 속성만 바꾼다.
//      저장된 레벨은 그대로다(PIE 월드는 사본). 바꾸는 것: HerbivoreConfig·WolfConfig → UEcoCreatureV3Trait 설정, 이주 끔, 웨이브 끔,
//      1초 에너지 소모·섭식 에너지 0 (에너지 주인은 v3), 낮밤 60 + 60초, 개체 상한, 지역마다 사슴 수·늑대 2·시작 자리.
//      모든 그룹의 계획·설정 생성·GUID 검사가 다 통과한 뒤에만 한꺼번에 쓴다 — 하나라도 실패하면 조정자를 하나도 건드리지 않는다.
//      바꾸기 전 팀 값은 따로 쥐어 둔다(시작 직전 검사가 실패하면 되돌린다).
//   2. 시작 자리 지면 검사 (팀 공개 함수 EcoCreatureMovement::ProjectSpawnPoint — 지면·경사·장애물·물):
//      - 스트리밍 없는 조정자: BeginPlay 안에서 바로 시작하므로 OnWorldBeginPlay 의 검사가 조정자가 볼 지형과 같다.
//      - 서식지 스트리밍 조정자: OnWorldBeginPlay 의 계획은 힌트일 뿐이다(지형이 덜 왔다). 조정자와 같은 조건(BeginPlay 뒤 0.25 초 이상 +
//        스트리밍 원천 완료)이 된 프레임에, 엔진 스트리밍 갱신(UWorld::Tick 의 InternalUpdateStreamingState) 뒤·조정자 OnWorldPostActorTick
//        앞인 TG_LastDemotable 틱에서 다시 검사해 덮어쓴다. 그래서 조정자 StartAuthority 와 같은 지형을 본다. 검사는 많아야 3 번이다.
//        못 채우면 팀 값으로 되돌리고 통합 모드를 끈다. 사슴은 절반(최소 4) 넘게 찾고 늑대를 다 찾으면 그 수로 시작한다.
//      - 조정자가 31 초 안에 시작하지 못하면(조정자 시간 초과 30 초) 오류 한 줄을 남기고 통합 모드를 끈다 (매 프레임 다시 검사하지 않는다).
//   3. 조정자가 개체를 만든 다음 프레임 앞: 지역마다 무대(학습 크기 한 변 120~220 m 정사각, 먹이 자리 중심, 지역 상자 안)와 v3 세계
//      (EcoWorldV3::FWorldState) 를 만든다. 은신처 원 = 레벨의 UEcoShelterSubsystem 은신처 중 무대 안이고 반경이 학습 범위(4~9 단위 =
//      8~18 m)인 것 + 우리가 실행 중에 놓는 AEcoShelterAnchor 4개(반경 = 무대 한 변의 0.1 배를 4~9 단위로 자름 — 넓이 8.4~12.6%,
//      학습 5~30%). 학습 범위 밖 레벨 은신처는 v3 원 목록에서만 뺀다(팀 Social 등록은 그대로). 목록은 RuntimeIndex 순으로 고정한다.
//   4. 전역 결정 시계 하나 (7.5 Hz, 평면 시험 경로의 시계·세션과 따로) 와 전역 스텝 t. t 는 팀 UEcoWorldClockSubsystem 시각에 맞춰
//      시작한다(낮 시작 = 스텝 0, 60 초 = 450 스텝). 어둠은 t 에서 계산한다(계약 7-6). 어긋남이 4 스텝을 넘으면 다시 맞춘다.
//   5. 기록 [EcoV3I] (지역마다 10 초) 와 디버그 표시 (콘솔 변수 eco.V3Debug 1). 산 사슴 밀도가 학습 하한(128 / 110² 마리/단위²) 아래로
//      내려가면 지역마다 경고 한 줄을 남긴다 (부활이 없어서 생기는 근사).
//      먹기 되먹임: 사슴 글자 = 행동 + 에너지 % (+ 이번 결정 스텝에 먹은 몫, 굶주림, 번식), 지역 집계 둘째 줄 = 무대 먹이 처음 대비 %·
//      최근 10 초 먹은 양·에너지 평균·굶주림 수. 기록 줄에는 구간 먹은 양·먹은 사슴 수·먹기 중 실제로 먹은 비율·무대 먹이 %·에너지 평균.
//      먹이는 v3 먹이 격자만 바뀐다 — 팀 지역 FoodAmount 에는 쓰지 않는다 (FEcoV3RegionContext 섭식 칸 설명).
//   6. 늑대 밤잠 점진화 (사람 결정 H1 10-14, 콘솔 변수 eco.IntegratedV3.GradualNight 기본 1 — Play 전에 바꾼다):
//      파이썬 configs/v3_real1_night_on.yaml 의 realism_night 를 엔진 무관 위협 모델로 옮긴 것(EcoThreatModel.h bRealismNight)을 켠다.
//      늑대는 해가 진 뒤 늑대마다 다른 지연(0~22 스텝, H(606, 세션 시드, StableAgentId))이 지나고, 사냥 중이 아니고, 16 m(8 단위) 안에 사슴이 없을 때 2 초 동안 걸음을
//      늦추다 눕는다. 그동안 사냥이 시작되거나 사슴이 다가오면 다시 일어난다. 깜깜하면(d = 1) 새 사냥을 시작하지 않고 쫓던 사냥만 마저
//      끝낸다. 새벽에는 하나씩 깨어 2 초에 걸쳐 걸음을 올린다. 해 진 뒤 깨어 있는 늑대의 속력 하한은 0.5 배다.
//      R1b 두뇌는 그대로다(관측 18·마스크 판 2). 학습 세계 밖 규칙이지만 R1b 측정(results/v3/real1)으로 허용했다(R3 명세 H1).
//      화면: 늑대 글자 '눕는 중'·'깨는 중' + 걸음 %, 사슴이 가까워·사냥 중이라 못 누우면 그 까닭. 기록: 잠듦·깸·눕기 시작·다시 일어남
//      한 줄씩(해 진 뒤 초, 가장 가까운 사슴 m), 10 초 줄에 밤잠 집계. 0 으로 두면 지금까지처럼 d ≥ 0.5 가 되는 순간 곧바로 잔다.
//   7. 사슴 얼기 막음 (사람 결정 10-15 (A) '지금 바로 없앰', 콘솔 변수 eco.IntegratedV3.NoFreeze 기본 1 — Play 전에 바꾼다):
//      세계 허용 칸(EcoWorldV3 FWorldConfig::WorldAllowed)의 FREEZE 를 0 으로 둔다. 실제 허용 = R1b 모델 허용 ∧ 세계 칸이라 마스크가
//      FREEZE 를 늘 막는다(파이썬 rep_policy.effective_allowed 와 같은 꼴 = R1b−F). 가중치는 그대로다 — R1b 가 얼던 자리에서는 R1b 의
//      다음 선호 행동이 나온다(R3 재학습 전 측정: 대부분 먹기 78%·도망 17%). 화면 'v3 R1b−F', 사슴 집계 '얼기(막힘) 0', 기록 줄에
//      '얼기 막힘: 실행 n · 얼기 칸이 열린 결정 n' (늘 0 이어야 한다). 0 으로 두면 R1b 그대로 얼기를 쓴다.
//   8. 늑대 식사 시간 (사람 결정 10-15 (B) '먹는 시간 주기 (약 5초)', 콘솔 변수 eco.IntegratedV3.WolfEatSeconds 기본 5 — Play 전에 바꾼다):
//      잡은 늑대는 시체 곁에 서서 약 5 초 먹고, 끝나면 곧바로 다시 사냥한다(포만 없음 — 늑대는 과식하게 둔다). 결정 스텝으로
//      5 ÷ (2/15 초) = 37.5 → 반올림 38 스텝(5.07 초)이고, 위협 설정의 식사 쿨다운(FThreatConfig::PredEatCd, 학습 5)을 38 로 바꾸고
//      식사 동안 서 있게(bEatInPlace) 한다. 0.67 이하(5 스텝 이하)는 옛 규칙 그대로다(학습 세계와 같다: 5 스텝 = 0.67 초, 그동안 배회).
//      파이썬 R3 세계의 같은 규칙은 overrides.pred_eat_cd 38 + features.threats.eat_in_place 다(같은 스텝 수·같은 제자리 꼴).
//      팀 표현은 '먹는 중' 깃발(FEcoPredatorStateFragment::EatCooldown > 0)과 속도 0 이면 '먹는 중' 동작을 보인다 — 기록 줄이
//      팀 늑대 표현 액터의 동작을 프레임마다 세어 확인한다. 화면: 늑대 글자 '늑대 식사 n초'(남은 초), 지역 집계 '늑대 식사 5초 제자리'.
//      기록 줄: 구간 포획·식사 중 늑대·스텝(그중 움직임)·돌진(앞 포획 뒤 3 초 안 = 이어 사냥, 식사 끝 뒤 3 초 안)·늑대별 포획 누적.
//      R1b 학습 세계 밖 규칙이다 — 파이썬 측정(R1b−F, v3_r1_on·v3_real1_night_on, 보정 시드 20000~20019)에서 사망이 줄고 G_γ 가
//      올라 허용했다(계획서 4-5b).
//   9. 사슴 도주 반사 거리 (사람 결정 10-15 (7) 야생 1단계 w3, 콘솔 변수 eco.IntegratedV3.WildFlight 기본 1 — Play 전에 바꾼다. 명령줄
//      -EcoV3WildFlight= 는 시작값, 옛 이름 -EcoV3KeepAway= 도 받는다): 두뇌 위의 세계 규칙 (EcoWorldV3.h '야생 1단계 (w3)', FWildFlightConfig).
//      10-15 (C) 의 경계 거리 실험 KeepAway(콘솔 변수 eco.IntegratedV3.KeepAway)는 이 규칙으로 바꾸고 지웠다 — 옛 동작은 남기지 않았다.
//      사냥 중인 늑대(먹는·배부른·자는 늑대 빼고)를 실제로 알아채면(시야·발소리) eco.IntegratedV3.AlertDistM(30 m) 안에서 '경계' — 두뇌가
//      먹기면 걸으며 먹고 늑대 반대쪽으로 멀어진다. eco.IntegratedV3.PanicDistM(15 m) 안이거나 다가오면 '도주' — 사냥 중인 늑대가 모두
//      eco.IntegratedV3.SafeDistM(40 m) 밖이 될 때까지 뛰고, 반대쪽 ±60°·30 m 안 은신처가 있으면 그쪽으로. 은신처 안이면 웅크린다.
//      먹는·쉬는 늑대는 경계만 일으킨다. 기록 셋째 줄 '경계 거리'(이름 그대로): 경계·도주·웅크림 시작, 끝난 도주의 평균 길이, 잡힌 사슴을
//      덮기로 가른 수, 식사 중 늑대 15 m 안 사슴. 0 으로 두면 지금과 비트 단위로 같다 (세계 칸이 모두 기본값).
//  10. 야생 1단계 (사람 결정 10-15 (7) '바뀐 규칙을 언리얼에서 보이게', 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md, 값 = 파이썬
//      configs/v3_wild1_mirror.yaml, 하루 900 스텝). 규칙마다 콘솔 변수 하나(기본 1 — Play 를 누르면 보인다. Play 전에 바꾼다)와 명령줄 시작값:
//      지방 비축 eco.IntegratedV3.WildReserve (-EcoV3WildReserve=, EcoWorldV3.h FWildReserveConfig): 배가 비어도 비축으로 3일(6분) 버티고
//      배·비축 모두 0 이어야 굶어 죽는다. 배 10% 밑이면 0.75 배 느리다. 비축으로 사는 사슴의 Vitals 에너지 거울은 아주 작은 양수라 팀 HP 감소가
//      먼저 죽이지 않는다 (죽음은 v3 DeathCause 한 길). 화면: 사슴 글자 '배고픔 비축 63%'·'비축 바닥'·'약함(느림)', 지역 둘째 줄 비축 평균·
//      비축으로 사는 사슴. 기록 넷째 줄 '<지역> 야생 |': 꺼내 씀·채움·약한 개체·스텝·약한 채로 잡힘·지금 비축 평균·최소 (앞 세 줄은 그대로).
//      늑대 포만 eco.IntegratedV3.WildSatiation (-EcoV3WildSatiation=, EcoThreatModel.h FThreatConfig::bWildSatiation): 먹기(5초)가 끝나면
//      반나절(450 스텝 = 60초) 사냥하지 않고 0.3 배 속력으로 어슬렁거린다. 자지 않는 한 사슴에게 보인다. 화면: 늑대 글자 '늑대 배부름·쉼 42초'.
//      기록 넷째 줄: 배불러 쉰·먹는 늑대·스텝 비율, 포만을 건 포획.
//      감지 eco.IntegratedV3.RealismVision (-EcoV3RealismVision=, 위협 시야 300° — 바로 뒤 60° 만 사각)·eco.IntegratedV3.RealismHearing
//      (-EcoV3RealismHearing=, 늑대 걸음이 빠를수록 멀리 들림 4~40 m, 어슬렁거리는 늑대는 4 m): R3 세계 값 그대로. 보임과 같은 칸이라
//      두뇌 관측(위협 수·거리·접근)·사건이 함께 바뀐다 (EcoObservationV3.h FHearingConfig·HearingRadius·ThreatFovCos).
//  11. 10-16 고침 (사용자 보고 '늑대가 먹기 시작하면 도망치던 사슴이 멈춘다'·'가장자리에서 늑대가 계속 잡아먹는다'·'은신처 안에서도 잡힌다',
//      명세 RL_V3_WILD1_SPEC.md 11절): 도주는 깨어 있는 늑대 모두에게서 SafeDistM 밖까지(먹는·배부른 늑대 곁에서 멈추지 않는다), 가장자리
//      10 m 안의 경계·도주는 벽을 따라·모서리 밖으로 (WildFlightConfig 의 bHoldAwake·EdgeR — eco.IntegratedV3.WildFlight 에 묶음).
//      은신처 안전 eco.IntegratedV3.ShelterSafe (-EcoV3ShelterSafe=, 기본 1, EcoThreatModel.h bShelterSafe·bShelterBlock): 은신처 원 안 사슴은
//      표적·포획에서 빠지고 늑대는 원 둘레를 따라 미끄러진다. 원 = 레벨에서 받은 은신처 + 우리 은신처 (FWorldConfig::Covers).
//      늑대 몸 여유 eco.IntegratedV3.WolfBodyMargin (-EcoV3WolfBodyMargin=, m, 기본 1 — 10-17, 파이썬 realism_shelter.wolf_margin 0.5): 늑대 중심은
//      은신처 반지름 + 1 m 밖에서 미끄러진다(화면에서 늑대 몸이 둘레 65 cm 안쪽 바위 테두리를 파고들지 않는다). 사슴 쪽은 반지름 그대로.
//      ShelterSafe 1 일 때만 쓴다(0 이면 팀 규칙이 자기 몸 여유 1 m 로 안전을 맡아 두 여유가 겹치지 않는다).
//  12. 10-17 팀 브랜치 통합 (origin/codex/social-shelter-handoff, 계획서 4-5b '10-17 팀 브랜치 통합'):
//      은신처 안전 규칙은 하나만 적용한다. ShelterSafe 1(기본) = 파이썬 realism_shelter. 조연우 님의 실제 은신처 규칙
//      eco.IntegratedV3.ProtectedRefuges (-EcoV3ProtectedRefuges=, 기본 1)는 그 위에 생명주기만 더한다 — 지워진 은신처는 원 반경 0(번호 유지),
//      늦게 등록된 무대 안 은신처는 끝에 추가(RefreshRefuges), 목표를 잃은 HIDE 사슴은 도주·먹기로, Social 도착은 몸이 원 안일 때만, [EcoRefuge] 기록.
//      ShelterSafe 0 일 때만 ProtectedRefuges 가 팀 안전 규칙(늑대 몸 여유 1 m·쓸고 지나가기 막기·갇힌 늑대 꺼내기·원 안 사슴 표적 제외)을 맡는다.
//      사슴 Social 연결 eco.IntegratedV3.SocialControl (-EcoV3SocialControl=, 기본 0 — 사람 결정 10-17 (8)): 0 이면 훅을 걸지 않는다.
//      Social 처리기는 돌며 기록만 하고 v3 사슴 움직임은 파이썬 세계 그대로다. 1 이면 무리 경보·은신처 슬롯이 v3 제어 뒤·이동 전에
//      사슴 제어를 바꾼다(EcoPolicyV3SocialBridge, FStepHooks::HerbControl — 팀 장면 확인용). 무리 반응은 뒤에 파이썬 야생 규칙으로 만든다.
//  13. 10-17 야생 2단계 1 (명세 RL_V3_WILD2_SPEC.md, 파이썬 configs/v3_wild2_mirror.yaml): 은신처 먹이 부족 eco.IntegratedV3.ShelterFood
//      (-EcoV3ShelterFood=, 기본 1 — 파이썬 realism_cover_food cap_frac·regen_frac 0.15): 은신처 원과 조금이라도 겹치는 먹이 셀의 용량과 재생 속도가
//      밖의 15% 다(EcoWorldV3.h FShelterFoodConfig·FFoodGrid::ApplyShelterFood). 은신처는 안전하지만 먹이가 적어 배고픈 사슴은 밖으로 나와야 한다.
//      늦게 등록되거나 지워진 은신처(RefreshRefuges)도 같은 식으로 다시 건다. 10초 기록 다섯째 줄 '[EcoV3I] <지역> 사냥·은신처 |' 는 늘 적는다:
//      사냥 성공률(늑대가 전력으로 쫓거나 덮친 사냥 가운데 잡음으로 끝난 몫 — world.py hunt_update 와 같은 정의), 은신처 안 사슴 시간, 둘레 밖 잡힘.
//      10-17 고침: 1b11c78 은 사용자 말 '추천대로 끄고 2~4번 진행해'(10-17)를 은신처 먹이 부족을 끄라는 뜻으로 잘못 읽어 기본을 0 으로 바꿨다. 그 말은 팀 무리 경보
//      연결(위 12, SocialControl)을 끄라는 뜻뿐이었고 사용자의 결정은 '은신처는 안전하지만 먹이가 적다'(10-14·10-15)라 기본을 1 로 되돌렸다.
//  14. 10-17 야생 2단계 2 늑대 무리 (명세 RL_V3_WILD2_SPEC.md, 파이썬 configs/v3_wild2_pack_mirror.yaml): 지역마다 늑대 수
//      eco.IntegratedV3.WolvesPerRegion (-EcoV3Wolves=, 기본 4 — 잠행 2·추격 2, 짝수 순번 = 잠행. 두뇌 학습 범위 2~12 안, 0~12 로 자름)와
//      협동 사냥 eco.IntegratedV3.PackHunt (-EcoV3PackHunt=, 기본 1 — 파이썬 wild_pack, EcoThreatModel.h '늑대 무리 협동 사냥'): 한 늑대가 사슴을
//      쫓는 동안 사냥 중이고 전력으로 달리지 않는 동료가 그 사슴이 달아날 곳(향하는 은신처의 문, 없으면 도주선 앞 12 m)으로 가서 기다린다.
//      은신처 진입 금지·몸 여유·포만·밤잠은 그대로다. 10초 기록 여섯째 줄 '[EcoV3I] <지역> 늑대 무리 |' (켰을 때만): 앞장·돕기·기다림·은신처 문
//      늑대·스텝, 늑대 포획·협동 포획(다른 앞장 늑대도 쫓던 사슴을 잡음) 누적.
//  15. 10-17 야생 2단계 3 세로 장애물 (명세 RL_V3_WILD2_SPEC.md 6절, 파이썬 configs/v3_wild2_obstacle_mirror.yaml obstacles): eco.IntegratedV3.Obstacles
//      (-EcoV3Obstacles=, 기본 1). 무대를 만들 때 무대 안 레벨의 충돌하는 스태틱 메시(폴리지 인스턴스 포함)를 읽기만 해서 원판으로 만들고(ScanStageObstacles —
//      액터·컴포넌트를 바꾸지 않는다), 사슴·늑대가 원판 둘레를 따라 미끄러지고 원판이 눈길을 가린다(EcoWorldV3.h FObstacleConfig). 지금 팀 레벨의 무대에는
//      충돌하는 나무·바위가 없어 원판이 0이다(10-17 읽기). eco.IntegratedV3.ObstacleExport(-EcoV3ObstacleExport=) 는 원판 JSON 을 쓰고,
//      eco.IntegratedV3.ObstacleImport(-EcoV3ObstacleImport=) 는 측정 전용으로 원판을 가져온다(레벨에 보이는 물체가 없는 원판). 10초 기록 일곱째 줄
//      '[EcoV3I] <지역> 장애물 |'(원판이 있을 때만).
//  16. 10-17 무대 나무 (사용자 '그럼 그냥 우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐', herbivore_rl/results/v3/wild2/trees/README.md):
//      eco.IntegratedV3.StageTrees (-EcoV3StageTrees=, 기본 1 → 10-18 부터 0, 아래 18). 레벨·콘텐츠는 바꾸지 않는다 — 무대를 만들 때 고정 배치 표(TreeLayoutV3.h, 파이썬
//      make_tree_layout.py 가 만든다 — 숲 24·고지 9·메마른 땅 0 그루)대로 팀 나무 메시(/Game/SHC/.../Beech_Tree)를 AStaticMeshActor 로 놓는다
//      (충돌 없음 — 메시 애셋은 그대로, 지면에 붙여 밑동을 10 cm 묻음, 그림자 켬). 줄기 원판(밑동 꼭짓점 반경 40.45 cm × 크기)은 세계 원판에 더하고
//      (레벨 읽기 원판과 합쳐 (x, y, r) 순), 레벨 읽기는 이 액터를 빼서 두 번 세지 않는다. 시작 자리 계획(PlanStage)은 줄기 원판(반지름 + 몸) 안 자리를 버린다.
//      파이썬 거울 configs/v3_wild2_trees_mirror.yaml 과 tree_layout.json 이 같은 원판이다. eco.IntegratedV3.Obstacles 0 이거나 무대 한 변이 표(120 m)와
//      다르거나 그 지역 원판을 가져왔으면(ObstacleImport) 놓지 않는다. 시작 줄 '[EcoV3I] <지역> 나무 |', eco.V3Debug 에서 줄기 원판은 초록 원.
//  17. 10-18 지역 날씨 (사용자 '일단 우리 테스트 레벨에도 날씨 적용되게 해 줘. 그리고 그 날씨와 장애물들을 바탕으로 만들어진 세계를 파이썬에 고대로 옮겨서
//      학습시킬 거야', 명세 RL_V3_WILD2_SPEC.md 11절, 파이썬 configs/v3_wild3_mirror.yaml wild_weather): eco.IntegratedV3.Weather (-EcoV3Weather=, 기본 1).
//      팀 설계대로 숲 = 비, 고지 = 눈, 메마른 땅 = 맑음 (세기 1, 지역마다 고정 — EcoWorldV3.h kRegionWeatherDefaults). 지역 덮기 eco.IntegratedV3.WeatherForest·
//      WeatherHighland·WeatherBarren (-EcoV3WeatherForest=rain:0.5 등, 측정·연출 전용). 비 = 시야 × 0.9·사슴 청각 × 0.5, 눈 = 시야 × 0.7·사슴 이동 × 0.6·
//      늑대 이동 × 0.85, 관측 visibility × 시야 (EcoWorldV3.h FWeatherConfig — 규칙은 엔진 무관 세계 층이 맡는다). 시작 줄 '[EcoV3I] 지역 날씨:'·
//      '[EcoV3I] <지역> 날씨 |', 10초 여덟째 줄 '[EcoV3I] <지역> 날씨 |'(지금 날씨·날씨별 스텝·감지 띠·들어서만). 연출 eco.IntegratedV3.WeatherVisuals
//      (-EcoV3WeatherVisuals=, 기본 1)는 EcoV3WeatherPresenter 가 맡는다 — 레벨·애셋은 그대로, 팀 나이아가라·소리를 실행 중 카메라 곁에 켠다.
//  18. 10-18 레벨 나무 (사용자 '일단 플레이시 장애물이 생성되게 하지 말고 그냥 우리 통합레벨에 배치를 해'): 16 의 나무를 통합 레벨에 진짜 액터로
//      놓았다 (편집기 전용 명령 -run=EcoV3PlaceTrees, EcoV3PlaceTreesCommandlet). 나무마다 팀 Beech_Tree 액터(충돌 없음, 꼬리표 EcoV3Tree)와
//      줄기 막이(엔진 원기둥, 게임에서 숨김, BlockAll, 꼬리표 EcoV3Trunk — 나무 액터에 붙어 함께 움직인다), 폴더 EcoV3_Trees. 그래서
//      eco.IntegratedV3.StageTrees 기본은 0 이다(예비 — 1 이면 레벨 나무가 없는 무대에만 실행 중에 놓는다). 레벨 읽기(ScanStageObstacles)는 줄기 막이를
//      원판으로 읽고, 표 자리와 1 cm 안이면 표 값을 그대로 쓴다(파이썬 거울 tree_layout.json 과 비트 단위로 같게 — SnapToLayout). 시작 자리 계획은
//      같은 원판을 피한다(GatherLevelTrunks → LevelTrunkDiscs). 무대를 만들 때 팀 이동 제약이 줄기에서만 막히는지 나무마다 재 본다
//      (ProbeLevelTrunks — 시작 줄 '[EcoV3I] <지역> 나무 |').
//  19. 10-18 두뇌 바꾸기 (사용자 '우리가 계획한 가중치 로더 써서 두뇌 바꿔주는 기술을 한번 적용해보자', EcoV3Brain.h): 사슴 두뇌는 이제 저장소
//      (FEcoV3BrainRegistry — 처음은 내장 R1b, 통합 모드는 얼기를 세계가 막아 R1b-F)의 지금 두뇌다. 콘솔 eco.V3Brain.Load <파일|builtin> 으로 Play 중에
//      바꾸면 결정 스텝 경계(SyncBrain)에서 바뀐다 — 사슴 몸·행동 상태는 그대로, 허용 칸 = 새 두뇌 ∧ 세계 칸. 시작 두뇌 eco.V3Brain.Startup(-EcoV3Brain=),
//      예정 바꾸기 eco.V3Brain.SwapAtSeconds·SwapFile(-EcoV3BrainSwapAt= -EcoV3BrainSwapTo=, 측정·시연용), 폴더 감시 eco.V3Brain.WatchFolder(기본 끔).
//      시작 줄 '[EcoV3I] 두뇌 시작 |', 바꿀 때 '[EcoV3I] 두뇌 바꿈 |', 10 초 아홉째 줄 '[EcoV3I] <지역> 두뇌 |'(두뇌 id, 구간 두뇌 스텝의 행동 몫과
//      늑대를 알 때의 행동 몫 — FEcoV3BrainTally). 평면 시험 경로(UEcoPolicyV3Subsystem)는 내장 두뇌 그대로다.
//
// 실제 스텝·입양·화면은 EcoPolicyV3IntegratedProcessors 가 한다.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoMigrationTypes.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Engine/EngineBaseTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "Templates/Function.h"
#include "Templates/UniquePtr.h"

#include "EcoPolicyClock.h"
#include "EcoV3Brain.h"
#include "EcoWorldV3.h"
#include "TreeLayoutV3.h"

#include "EcoPolicyV3IntegratedSubsystem.generated.h"

class AEcologyRegion;
class AActor;
class UMassEntityConfigAsset;
class UStaticMesh;
class UEcoPolicyV3IntegratedSubsystem;

DECLARE_LOG_CATEGORY_EXTERN(LogEcoPolicyV3I, Log, All);

namespace EcoV3Integrated
{
	/** 늑대 화면·기록 상태 (학습 위협 상태에서 읽는다). */
	enum class EWolfState : uint8
	{
		Roam,      // 배회
		Stalk,     // 잠행 (잠행형이 표적을 보고 천천히 다가감)
		Pounce,    // 돌진
		Exhaust,   // 지침 (돌진 실패 뒤)
		Chase,     // 추격 (추격형이 표적을 봄)
		Eat,       // 식사 (포획 뒤 쿨다운)
		Sleep,     // 잠 (주행성. 밤잠 점진화를 끄면 어둠 0.5 이상, 켜면 늑대별 잠)
		Settle,    // 눕는 중 (밤잠 점진화: 걸음을 늦추는 2 초)
		Waking,    // 깨는 중 (밤잠 점진화: 깨어 걸음을 올리는 중, 또는 눕다가 다시 일어나는 중)
		Count
	};

	/**
	 * 굶주림 표시 선: 에너지 15% 아래. 걷는 먹기(대사 0.002/스텝)로 75 스텝 = 10 초, 서서 먹기로 약 14 초, 뛰면 4 초 안에 굶어 죽는 선이다.
	 * 표시·기록 전용 (규칙이 아니다).
	 */
	inline constexpr double kStarvingEnergy = 0.15;
	// 야생 (w1) 화면·기록: 비축이 이 밑이면 '비축 바닥 가까움' (글자 빨강·기록 줄 수)
	inline constexpr double kLowReserve = 0.25;
	/** '최근 10 초 먹은 양' 창 = 결정 스텝 75 개 (7.5 Hz × 10 초, 시뮬레이션 시간). */
	inline constexpr int32 kRecentEatSteps = 75;
	/** 번식 표시를 남기는 결정 스텝 수 (약 1.5 초). */
	inline constexpr int64 kReproMarkSteps = 11;
	/** 이어 사냥 창 = 결정 스텝 22 개 (3 초, R3 재학습 전 측정 results/v3/r3/pre 의 '이어 사냥'과 같은 창). */
	inline constexpr int64 kChainWindowSteps = 22;
	/** 기록 '식사 중 늑대 15 m 안 사슴'의 거리 (단위 7.5 = 15 m 고정 — 경계 거리 콘솔 변수와 무관하게 규칙 켬·끔을 견준다). 기록 전용. */
	inline constexpr double kNearEatingWolfUnits = 7.5;

	/**
	 * 늑대 상태 (화면·기록). Cfg 는 그 지역 세계의 위협 설정 (FWorldState::ThreatCfg) — 밤잠 점진화를 켠 세계만 눕는 중·깨는 중이 나온다.
	 * 우선순위: 잠 > 눕는 중 > 돌진·지침 > 식사 > 추격·잠행 > 깨는 중 > 배회.
	 */
	ADAPTIVEECOSYSTEM_API EWolfState WolfStateOf(const EcoWorldV3::FThreatAgent& Agent,
												 const EcoThreatV3::FThreatConfig& Cfg = EcoThreatV3::FThreatConfig());
	ADAPTIVEECOSYSTEM_API const TCHAR* WolfStateNameKo(EWolfState State);

	/**
	 * 늑대 머리 위 글자 (eco.V3Debug 1): '늑대 눕는 중 (추격형) 걸음 40%'. 밤잠 점진화를 켠 세계에서 깨어 있는 주행성 늑대가 이번 스텝에
	 * 누울 차례인데 못 누웠으면 ' · 사슴 곁이라 안 누움' / ' · 사냥 중이라 안 누움', 눕는 중이 아닌데 깜깜해 새 사냥을 안 하면 ' · 깜깜해 새 사냥 안 함'.
	 * 식사 중이면 '늑대 식사 3.2초 (잠행형)' — 남은 식사 = 쿨다운 × 결정 스텝 2/15 초 (0.1 초 단위).
	 */
	ADAPTIVEECOSYSTEM_API FString WolfLabel(const EcoWorldV3::FThreatAgent& Agent, const EcoThreatV3::FThreatConfig& Cfg, double Dark,
											FColor& OutColor);
	ADAPTIVEECOSYSTEM_API const TCHAR* BehaviorNameKo(int32 Behavior);

	/**
	 * 산 사슴 머리 위 글자와 색 (eco.V3Debug 1). '먹기 72%' = 행동 + 에너지 %. 이번 결정 스텝에 먹이 칸에서 실제로 먹었으면
	 * ' +3.0' (먹은 몫을 에너지 %p 로, 0.05 미만이면 '+' 만), 에너지 15% 아래면 ' 굶주림'(빨강), bRecentRepro 면 ' 번식'.
	 * 색은 행동 색 (먹기 초록·도망 노랑·숨기 파랑·얼기 흰색), 굶주림만 빨강.
	 * KeepMode = 이번 스텝의 도주 반사 덮기 (FHerbDecision::KeepActive): 행동 이름 대신 '경계(먹으며 멀어짐)'(주황, 두뇌가 먹기일 때만)·
	 * '도주(안전해질 때까지)'(진한 주황)·'웅크림(은신처·경계)'(파랑). 0 이면 지금 그대로.
	 * bReserveOn = 지방 비축을 켠 세계 (야생 w1): 에너지 15% 아래면 ' 굶주림' 대신 ' 배고픔 비축 63%'(빨강, 비축으로 버티는 중),
	 * 비축 0 이면 ' 비축 바닥', 배 10% 밑이면 ' 약함(느림)'. 배는 괜찮은데 비축이 25% 밑이면 ' 비축 20%'. 거짓이면 지금 그대로.
	 */
	ADAPTIVEECOSYSTEM_API FString DeerLabel(const EcoRepertoireV3::FRepState& Rep, const EcoWorldV3::FHerbBody& Body, bool bRecentRepro,
											FColor& OutColor, int32 KeepMode = EcoWorldV3::kKeepNone, bool bReserveOn = false);
	/** 도주 반사 덮기 이름 (기록·화면): 두뇌 / 경계(먹으며 멀어짐) / 도주(안전해질 때까지) / 웅크림(은신처·경계). */
	ADAPTIVEECOSYSTEM_API const TCHAR* KeepModeNameKo(int32 KeepMode);

	/** 지역 늑대 순번(StableAgentId 순) → 성질. 짝수 = 잠행-돌진형, 홀수 = 근접 추격형. 모두 주행성(밤에 잔다), 원거리형 없음. */
	ADAPTIVEECOSYSTEM_API EcoThreatV3::FThreatSpec WolfSpecForOrdinal(int32 Ordinal, double PredSpeedMult);
}

/** 통합 모드 설정 (콘솔 변수·명령줄에서 읽는다. 시험은 직접 채운다). */
struct ADAPTIVEECOSYSTEM_API FEcoV3IntegratedSettings
{
	/** 학습 사슴 수 N (configs/default.yaml, 부활로 늘 128). 학습 밀도 하한 = 이 값 ÷ 맵 한 변 최대(110 단위)². */
	static constexpr int32 kTrainDeer = 128;
	/** 학습 은신처 반경 범위 (단위, UEcoPolicyV3Subsystem::CheckTrainingRange 와 같다 — 8~18 m). */
	static constexpr double kCoverRadiusLoUnits = 4.0;
	static constexpr double kCoverRadiusHiUnits = 9.0;

	int64 Seed = 20000;                 // 세션 시드 (지연 해시 Seed·세계 난수·시작 자리 난수)
	int32 DeerPerRegion = kTrainDeer;   // 학습 N 과 같은 128 — 무대 60~110 단위 어디서나 시작 밀도가 학습 범위 안이고, 피식 EMA 분모도 학습과 같다.
										// 부활이 없어 줄기만 한다 (60 단위 무대는 사망 90 마리까지 학습 밀도 하한 위)
	int32 WolvesPerRegion = 4;          // 잠행 2 + 추격 2 (eco.IntegratedV3.WolvesPerRegion 기본 4, 10-17 야생 2단계 2 — 학습 보통 위협 2~12, 잠행 비율 30~70%)
	double StageSizeUnits = 60.0;       // 무대 한 변 (단위, 학습 60~110 = 120~220 m)
	double PredSpeedMult = 0.8;         // 늑대 속력 = 사슴 뛰기 900 cm/s × 0.8 = 720 cm/s (학습 0.6~0.95)
	bool bGradualNight = true;          // 늑대 밤잠 점진화 (eco.IntegratedV3.GradualNight 기본 1, 사람 결정 H1 10-14). 거짓 = d ≥ 0.5 에 곧바로 잠
	bool bNoFreeze = true;              // 사슴 얼기 막음 (eco.IntegratedV3.NoFreeze 기본 1, 사람 결정 10-15 (A)). 거짓 = R1b 그대로 얼기를 쓴다
	bool bProtectedRefuges = true;      // 실제 은신처 생명주기 (eco.IntegratedV3.ProtectedRefuges 기본 1, 조연우 님 a88eac8). 안전은 bShelterSafe 가 맡고,
										// bShelterSafe 거짓일 때만 팀 규칙(늑대 몸 여유 1 m·쓸고 지나가기 막기)이 안전을 맡는다 (10-17 통합, 하나만 적용)
	bool bSocialControl = false;        // 사슴 Social 행동 연결 (eco.IntegratedV3.SocialControl 기본 0, 사람 결정 10-17 (8)). 참 = 조연우 님 22eb1b6 HerbControl 훅을 건다
	double WolfEatSeconds = 5.0;        // 늑대 식사 길이 (초, eco.IntegratedV3.WolfEatSeconds 기본 5, 사람 결정 10-15 (B)). 0.67 이하 = 옛 규칙
	bool bWildFlight = true;            // 사슴 도주 반사 거리 (eco.IntegratedV3.WildFlight 기본 1, 야생 w3 — 경계 거리 KeepAway 를 바꿨다). 거짓 = 두뇌 그대로
	bool bFlightHoldAwake = true;       // 도주 붙잡기 (eco.IntegratedV3.FlightHoldAwake 기본 1, 10-16 hold_awake). 거짓 = 사냥 중인 늑대만 도주를 붙잡는다 (857da45)
	bool bFlightEdgeAvoid = true;       // 가장자리 굽히기 (eco.IntegratedV3.FlightEdgeAvoid 기본 1, 10-16 edge_r 5). 거짓 = 굽히지 않는다 (857da45)
	double AlertDistM = 30.0;           // 경계 거리 alert_r (m, eco.IntegratedV3.AlertDistM) — 사냥 중인 늑대를 이 안에서 알아채면 먹으며 멀어진다
	double PanicDistM = 15.0;           // 도주 거리 flight_r (m, eco.IntegratedV3.PanicDistM) — 이 안이거나 다가오면 뛰어서 달아난다
	double SafeDistM = 40.0;            // 안전 거리 safe_r (m, eco.IntegratedV3.SafeDistM) — 사냥 중인 늑대가 모두 이 밖일 때까지 도주
	bool bWildReserve = true;           // 사슴 지방 비축 (eco.IntegratedV3.WildReserve 기본 1, 사람 결정 10-15 (7) 야생 1단계 w1). 거짓 = E 0 이면 곧바로 굶음
	bool bWildSatiation = true;         // 늑대 포만 (eco.IntegratedV3.WildSatiation 기본 1, 야생 w2). 거짓 = 식사가 끝나면 곧바로 사냥
	bool bRealismVision = true;         // 위협 시야 300° (eco.IntegratedV3.RealismVision 기본 1, R3 realism_vision). 거짓 = 앞쪽 120°
	bool bRealismHearing = true;        // 늑대 발소리 (eco.IntegratedV3.RealismHearing 기본 1, R3 realism_hearing). 거짓 = 소리 없음
	bool bShelterSafe = true;           // 은신처 안전·늑대 진입 금지 (eco.IntegratedV3.ShelterSafe 기본 1, 10-16 — R3 realism_shelter). 거짓 = 은신처 안에서도 잡힘
	double WolfBodyMarginM = 1.0;       // 늑대 몸 여유 (m, eco.IntegratedV3.WolfBodyMargin 기본 1, 10-17 — 파이썬 realism_shelter.wolf_margin 0.5). bShelterSafe 일 때만.
	bool bShelterFood = true;           // 은신처 먹이 부족 (eco.IntegratedV3.ShelterFood 기본 1, 10-17 야생 2단계 1 — 파이썬 realism_cover_food 0.15. 10-17 고침으로 기본 1 로 되돌림).
										// 거짓 = 은신처 셀 재생만 0.3배 (R1b 학습 세계)
	bool bPackHunt = true;              // 늑대 무리 협동 사냥 (eco.IntegratedV3.PackHunt 기본 1, 10-17 야생 2단계 2 — 파이썬 wild_pack, 값 = FPackHuntConfig 기본값)
	bool bObstacles = true;             // 세로 장애물 (eco.IntegratedV3.Obstacles 기본 1, 10-17 야생 2단계 3 — 파이썬 obstacles). 레벨의 충돌하는 나무·바위를 원판으로 읽어
										// 사슴·늑대가 둘레를 따라 미끄러지고 시선이 가린다. 원판이 없는 무대는 아무것도 바뀌지 않는다
	bool bObstacleDetour = true;        // 장애물 돌아가기 (eco.IntegratedV3.ObstacleDetour 기본 1, 10-17 끼임 고침 — 파이썬 obstacles.detour, 값 = FDetourConfig 기본값).
										// 막히면 가장 적게 돈 빈 방향으로 돌아간다. bObstacles 이고 원판이 있을 때만 쓴다. 거짓 = 미끄러짐만
	FString ObstacleExportPath;         // 원판 목록 JSON 내보내기 (eco.IntegratedV3.ObstacleExport, 빈 문자열 = 안 함 — 파이썬 거울 짝 비교용)
	FString ObstacleImportPath;         // 원판 목록 JSON 가져오기 (eco.IntegratedV3.ObstacleImport, 빈 문자열 = 안 함 — 측정 전용: 레벨 원판 대신 이 원판.
										// 레벨에 보이는 물체가 없는 원판이라 화면용이 아니다. 파이썬 거울과 같은 원판으로 견줄 때만 쓴다)
	bool bStageTrees = false;           // 실행 중 무대 나무 (eco.IntegratedV3.StageTrees 기본 0, 10-18 — 나무는 통합 레벨에 놓은 액터다, 꼬리표 EcoV3Tree·EcoV3Trunk).
										// 참 = 예비: 레벨 나무가 없는 무대에만 배치 표 TreeLayoutV3.h 대로 팀 나무를 실행 중에 놓고 줄기 원판을 세계에 넣는다
										// (10-17 그대로). bObstacles 일 때만 놓는다
	bool bWeather = true;               // 지역 날씨 (eco.IntegratedV3.Weather 기본 1, 10-18 야생 3단계 — 파이썬 configs/v3_wild3_mirror.yaml wild_weather). 숲 비·고지 눈·
										// 메마른 땅 맑음 (EcoWorldV3.h kRegionWeatherDefaults = 팀 설계). 거짓 = 날씨 없음 (10-17 그대로 — 비트 단위로 같다)
	FString WeatherForest;              // 지역 날씨 덮기 (eco.IntegratedV3.WeatherForest·WeatherHighland·WeatherBarren, '날씨[:세기]' — 날씨 = clear·rain·snow
	FString WeatherHighland;            //   (맑음·비·눈도 받음), 세기 0~1 (비·눈 기본 1). 빈 값 = 팀 설계 기본 (kRegionWeatherDefaults). 측정·연출 전용 —
	FString WeatherBarren;              //   파이썬 거울과 다르게 하면 짝 비교가 맞지 않는다
	bool bWeatherVisuals = true;        // 비·눈 연출 (eco.IntegratedV3.WeatherVisuals 기본 1, 10-18 — EcoV3WeatherPresenter: 카메라가 비·눈 지역 안이면 카메라 곁에
										// 팀 Rain_System·A_Rain_Cue·NS_Blizzard). 그리기만 바뀐다 (규칙·관측 그대로). 그릴 수 없는 실행·전용 서버는 늘 끔
	double WeatherRainDensity = 1.0;    // 빗줄기 수 배수 (eco.IntegratedV3.WeatherRainDensity 기본 1 = 팀 블루프린트와 같은 User.SpawnRate 500 — 낮에는 옅다. 화면 전용, 0.1~10)
	int32 ExtraCoverCount = 4;          // 우리가 놓는 은신처 수 (무대 1/4·3/4 지점)
	double ExtraCoverRadiusFrac = 0.1;  // 우리 은신처 반경 = 무대 한 변 × 이 값을 4~9 단위로 자름 (ExtraCoverRadiusUnits)
	double WolfStartCornerFrac = 0.4;   // 늑대 시작 = 무대 중심에서 (±한 변 × 이 값, ±한 변 × 이 값) 모서리 쪽. 사슴은 무대 전체 균등
	double WolfMinStartDistCm = 2800.0; // 늑대는 모든 사슴에게서 28 m 밖에서 시작 (늑대 시야 14 단위)
	double DeerMinSpacingCm = 150.0;    // 시작 자리끼리 최소 간격
	float LogIntervalSeconds = 10.0f;   // [EcoV3I] 지역 기록 주기 (시뮬레이션 초)

	/**
	 * 우리 은신처 반경 (단위). 무대 60 단위 = 6 단위(12 m, 4 개 넓이 12.6%), 110 단위 = 9 단위(18 m, 8.4%) — 무대 크기를 바꿔도 반경·넓이가
	 * 학습 범위(반경 4~9 단위, 넓이 5~30%) 안이다.
	 */
	double ExtraCoverRadiusUnits(double SizeUnits) const
	{
		return FMath::Clamp(ExtraCoverRadiusFrac * SizeUnits, kCoverRadiusLoUnits, kCoverRadiusHiUnits);
	}

	/**
	 * 늑대 몸 여유의 세계 칸 (m → 단위 = m × 100 ÷ 200, 1 m = 0.5 단위 = 파이썬 configs/v3_wild1_mirror.yaml realism_shelter.wolf_margin).
	 * 은신처 안전(bShelterSafe)을 끄면 0 — 그때는 팀 규칙이 자기 몸 여유(FWorldConfig::PredatorRefugeMargin)로 안전을 맡아 두 여유가 겹치지 않는다.
	 * 음수·수가 아닌 값은 0, 5 m 에서 자른다.
	 */
	double WolfBodyMarginUnits() const
	{
		if (!bShelterSafe || !FMath::IsFinite(WolfBodyMarginM) || WolfBodyMarginM <= 0.0)
		{
			return 0.0;
		}
		return FMath::Min(WolfBodyMarginM, 5.0) * 100.0 / EcoRepertoireV3::kUnitCm;
	}

	/** 학습 세계의 식사 쿨다운 (결정 스텝, configs/default.yaml pred_eat_cd 5 = 0.67 초 — 위협 설정 기본값). */
	static int32 TrainEatSteps() { return EcoThreatV3::FThreatConfig().PredEatCd; }

	/**
	 * 늑대 식사 길이 (결정 스텝) = 반올림(초 ÷ 2/15 초), 0.5 는 올린다. 학습 5 스텝 아래로 내리지 않고 900 스텝(2 분)에서 자른다.
	 * 5 초 = 37.5 → 38 스텝 (5.07 초), 0.67 초 = 5.025 → 5 스텝 (옛 규칙), 1 초 = 7.5 → 8 스텝.
	 */
	int32 WolfEatSteps() const
	{
		if (!FMath::IsFinite(WolfEatSeconds))
		{
			return TrainEatSteps();
		}
		const int32 Steps = FMath::FloorToInt32(WolfEatSeconds / EcoRepertoireV3::kStepSeconds + 0.5);
		return FMath::Clamp(Steps, TrainEatSteps(), 900);
	}

	/** 식사가 학습보다 긴가 (그때만 쿨다운을 바꾸고 식사 동안 세운다). 아니면 옛 규칙 그대로 (5 스텝, 그동안 배회 — 학습 세계·골든과 같다). */
	bool LongWolfEat() const { return WolfEatSteps() > TrainEatSteps(); }

	/**
	 * 도주 반사 거리의 세계 칸 (m → 단위 = m × 100 ÷ 200). 끄면 기본값(꺼짐) 그대로라 세계가 읽는 값이 바꾸기 전과 같다.
	 * 음수·수가 아닌 값은 기본값으로, 0 ~ 200 m 로 자르고, 안전 거리는 경계·도주 거리보다 작지 않게 올린다 (도주가 풀리자마자 다시 걸리지 않게).
	 * 나머지 계수(접근 0.9·경계 무게 1.5·은신처 ±60°/30 m·웅크림·벽 2 m)는 FWildFlightConfig 기본값 = configs/v3_wild1_mirror.yaml.
	 */
	EcoWorldV3::FWildFlightConfig WildFlightConfig() const
	{
		EcoWorldV3::FWildFlightConfig K;
		if (!bWildFlight)
		{
			return K;
		}
		auto Units = [](double M, double Def)
		{
			const double V = FMath::IsFinite(M) && M >= 0.0 ? FMath::Min(M, 200.0) : Def;
			return V * 100.0 / EcoRepertoireV3::kUnitCm;
		};
		K.bEnabled = true;
		K.AlertR = Units(AlertDistM, 30.0);
		K.FlightR = Units(PanicDistM, 15.0);
		K.SafeR = FMath::Max(Units(SafeDistM, 40.0), FMath::Max(K.AlertR, K.FlightR));
		// 10-16 고침 (configs/v3_wild1_mirror.yaml hold_awake true·edge_r 5): 도주는 깨어 있는 늑대 모두에게서 SafeR 밖까지, 가장자리 10 m 안은 벽을 따라
		// 두 고침은 따로 끌 수 있다 (eco.IntegratedV3.FlightHoldAwake·FlightEdgeAvoid, 고치기 전·뒤 영상용). 끄면 857da45 와 같다
		K.bHoldAwake = bFlightHoldAwake;
		K.EdgeR = bFlightEdgeAvoid ? 5.0 : 0.0;
		return K;
	}

	/** 사슴 Deer 마리가 한 변 SizeUnits 무대에서 학습 밀도 하한(128 / 110² 마리/단위²) 아래인가. */
	static bool IsBelowTrainingDensity(int32 Deer, double SizeUnits)
	{
		const double MaxSide = 110.0;
		return SizeUnits > 0.0 && static_cast<double>(Deer) * MaxSide * MaxSide < static_cast<double>(kTrainDeer) * SizeUnits * SizeUnits;
	}

	/**
	 * 날씨 글자 '날씨[:세기]' (구분은 ':'·','·공백 아무거나) → (EcoWorldV3::kWeather*, 세기). 날씨 = clear·rain·snow 또는 맑음·비·눈 (대소문자 무관),
	 * 세기는 [0, 1] 로 자르고 빠지면 비·눈 1, 맑음은 늘 0. 못 읽으면 거짓 (OutKind·OutIntensity 그대로).
	 */
	static bool ParseWeather(const FString& Text, int32& OutKind, double& OutIntensity);

	/**
	 * 지역 세계의 날씨 설정 (10-18 야생 3단계). bWeather 거짓이면 끔(기본값). 켜면 그 지역의 팀 설계 기본(kRegionWeatherDefaults — 표에 없는 지역은 맑음)에
	 * 지역 덮기 글자(WeatherForest 등)를 읽어 덮는다. 배수 계수·visibility 는 FWeatherConfig 기본값 = 파이썬 거울 계수.
	 */
	EcoWorldV3::FWeatherConfig WeatherFor(FName RegionId) const;

	/** 콘솔 변수 eco.IntegratedV3.* 에서 읽는다 (명령줄 -EcoV3Seed= -EcoV3DeerPerRegion= 은 그 콘솔 변수의 시작값이다). */
	static FEcoV3IntegratedSettings FromConsole();
};

/** 한 지역 무대 계획 (조정자 시작 전에 정한다). */
struct ADAPTIVEECOSYSTEM_API FEcoV3StagePlan
{
	FName RegionId;
	int32 GroupIndex = INDEX_NONE;
	FVector CenterCm = FVector::ZeroVector;   // 무대 중심 (Z = 높이 힌트)
	double SizeUnits = 60.0;
	TArray<FVector> DeerPoints;               // 사슴 시작 자리 (cm)
	TArray<FVector> WolfPoints;               // 늑대 시작 자리 (cm)
	int32 WantDeer = 0;                       // 계획한 수 (다시 검사해도 이 수를 채우려 한다)
	int32 WantWolves = 0;
	bool bStageInside = false;                // 무대 네 모서리가 지역 상자 안
	bool bGrounded = false;                   // 모든 시작 자리를 지면 검사로 골랐다 (스트리밍 조정자는 시작 직전 검사 뒤에만 참)
	bool bComplete = false;                   // 사슴·늑대 수를 다 채웠다
	std::vector<double> TrunkDiscs;           // 시작 자리가 피한 줄기 원판 (x, y, r) × K, 무대 단위 — 레벨 나무 줄기(10-18) 또는 실행 중 나무 표(10-17)
	bool bLevelTrunks = false;                // TrunkDiscs 가 레벨 나무 줄기다 (이 무대에는 실행 중 나무를 놓지 않는다)

	/** 무대 (0, 0) 의 cm (XY). */
	FVector OriginCm() const { return FVector(CenterCm.X - 0.5 * SizeUnits * 200.0, CenterCm.Y - 0.5 * SizeUnits * 200.0, CenterCm.Z); }
	bool IsInsideStage(const FVector& P, double MarginCm = 0.0) const
	{
		const double Half = 0.5 * SizeUnits * 200.0 - MarginCm;
		return FMath::Abs(P.X - CenterCm.X) <= Half && FMath::Abs(P.Y - CenterCm.Y) <= Half;
	}
};

/** 최근 포획 자리 (디버그 표시). */
struct FEcoV3IntegratedCatchMark
{
	FVector Location = FVector::ZeroVector;
	double Time = 0.0;
};

/**
 * 늑대 식사·이어 사냥·팀 화면 확인 집계 (누적, 사람 결정 10-15 (B)). 기록 줄은 지난 줄과의 차이를 쓴다. 기록·시험 전용 (규칙이 아니다).
 * '이어 사냥' = 그 늑대가 앞 포획 뒤 3 초 안에 시작한 돌진 (식사가 3 초보다 길면 늘 0). '식사 끝 3 초 안' = 앞 포획 뒤
 * (식사 스텝 + 22 스텝) 안 — 식사를 마치자마자 곁의 사슴에게 돌진했는가.
 */
struct FEcoV3WolfEatTally
{
	int64 Catches = 0;              // 늑대 포획 (늑대·스텝. 같은 사슴을 둘이 잡으면 둘 다 센다 — 파이썬 got 과 같다)
	int64 EatSteps = 0;             // 식사 중(포획 뒤 쿨다운으로 사냥하지 않음) 늑대·스텝
	int64 EatMoved = 0;             // 그중 움직인 늑대·스텝 (제자리 식사면 0)
	int64 Pounces = 0;              // 잠행형 돌진 시작
	int64 ChainPounces = 0;         // 그 늑대가 앞 포획 뒤 3 초(22 스텝) 안에 시작한 돌진
	int64 PostEatPounces = 0;       // 앞 포획 뒤 (식사 스텝 + 22 스텝) 안에 시작한 돌진
	int64 RepeatCatches = 0;        // 앞 포획이 있는 늑대의 포획
	int64 PostEatCatches = 0;       // 그중 앞 포획 뒤 (식사 스텝 + 22 스텝) 안 포획
	int64 EatFlagFrames = 0;        // 팀 늑대 표현 액터: 식사 깃발(bEating)이 선 늑대·프레임
	int64 EatMotionFrames = 0;      //   그중 팀 화면 동작이 '먹는 중'(서서 먹기)
	int64 EatWalkFrames = 0;        //   그중 걷기·뛰기 (깃발이 섰는데 움직인다 — 잡은 스텝의 이동을 보간하는 0.13 초가 여기 든다)
};

/**
 * 무대 안 세로 장애물 읽기 결과 (야생 2단계 3, 명세 RL_V3_WILD2_SPEC.md 6절). 레벨을 읽기만 한다 — 액터·컴포넌트를 바꾸지 않는다.
 * 원판 = 무대 안의 충돌하는 스태틱 메시(인스턴스 하나하나 포함 — 폴리지·HISM)의 충돌 상자 가로 반지름. 팀 이동 제약(EcoCreatureMovement::ConstrainStep)이
 * 막는 것과 같은 조건(쿼리 충돌 켬 ∧ WorldStatic 채널 막음)만 넣는다. 기록 칸은 [EcoV3I] '<지역> 장애물' 시작 줄에 적는다.
 */
struct ADAPTIVEECOSYSTEM_API FEcoV3ObstacleScan
{
	static constexpr double kMinRadiusCm = 25.0;   // 이보다 가는 것은 뺀다 (사슴이 비켜 디딘다 — 어림)
	static constexpr double kMinHeightCm = 50.0;   // 이보다 낮은 것은 뺀다 (뛰어넘거나 디딘다 — 어림)
	static constexpr int32 kMaxDiscs = 512;        // 무대마다 많아야 (스텝 비용 상한)

	std::vector<double> Discs;      // (x, y, r) × K, 무대 단위 (1 단위 = 200 cm). x·y 순으로 정렬
	int32 SeenMeshes = 0;           // 무대 안 메시 (컴포넌트 하나·인스턴스 하나를 하나로 센다)
	int32 NoCollision = 0;          // 충돌 없음 (풀·덤불 장식·HLOD)
	int32 Tiny = 0;                 // 가로 반지름 kMinRadiusCm 밑
	int32 Low = 0;                  // 높이 kMinHeightCm 밑
	int32 InCover = 0;              // 중심이 은신처 원 안 (은신처 안은 원판으로 넣지 않는다 — 덤불·바위 장식이 은신처 원 자체다)
	int32 RefugeDecor = 0;          // 은신처 액터(AEcoShelterAnchor·AEcoRefugeHabitat)의 장식 메시
	int32 Capped = 0;               // kMaxDiscs 를 넘어 뺀 수
	int32 NearEdge = 0;             // 넣은 원판 가운데 무대 벽에서 r + 2 × 몸(30 cm) 안 — 벽과 원판 사이에 사슴이 낄 수 있다 (기록만, 그대로 넣는다.
									// 파이썬 무작위 배치는 이런 원판을 놓지 않는다 — world.py OB_EDGE_BODIES)
	TMap<FString, int32> KeptByMesh;          // 원판으로 넣은 메시 이름 → 수
	TMap<FString, int32> NoCollisionByMesh;   // 충돌이 없어 뺀 메시 이름 → 수
	int32 GroundCells = 0;          // 지면 검사 2 m 격자 칸 (기록만 — 원판에 넣지 않는다)
	int32 SteepCells = 0;           // 그중 지면 경사가 팀 이동 한계(법선 Z < 0.65) 밖
	int32 WaterCells = 0;           // 그중 물(내비 제외 볼륨) 안
	int32 NoGroundCells = 0;        // 그중 지면을 못 찾음
	// 레벨 나무 (10-18, 통합 레벨에 놓은 줄기 막이 — 꼬리표 EcoV3Trunk). 읽기에 지역 이름을 주었을 때만 표와 맞춘다
	TArray<uint8> IsLevelTree;      // 원판마다 레벨 나무 줄기 막이에서 왔나 (Discs 순서)
	int32 LevelTrees = 0;           // 넣은 원판 가운데 레벨 나무 줄기
	int32 LevelTreesSnapped = 0;    // 그중 표 줄기와 1 cm 안이라 표 값을 그대로 쓴 수 (파이썬 거울 tree_layout.json 과 비트 단위로 같다)
	int32 LevelTreesUnmatched = 0;  // 그중 표 줄기와 맞지 않는 수 (누가 옮겼거나 크기를 바꿨다 — 읽은 값 그대로 쓴다)
	double LevelTreeMaxSnapCm = 0.0;   // 표 값으로 바꾼 줄기의 읽은 값 ↔ 표 값 차이 최대 (cm, 중심·반지름 가운데 큰 것)

	int32 Num() const { return static_cast<int32>(Discs.size() / 3); }
	/** 원판 넓이 합 ÷ 무대 넓이 (겹침은 두 번 센다). */
	double AreaFrac(double SizeUnits) const;
};

/**
 * 무대 나무 놓기 결과 (10-17 사용자 '우리 쪽 테스트 레벨에 저 사람이 만든 장애물들 적절히 배치해 봐', 배치 표 TreeLayoutV3.h). 레벨은 바꾸지 않는다 —
 * 실행 중 액터만 놓는다(충돌 없음). 원판은 세계 원판(Sim.Config.Obstacles)에 레벨 읽기 원판과 합쳐 넣는다.
 */
struct ADAPTIVEECOSYSTEM_API FEcoV3StageTrees
{
	std::vector<double> Discs;              // 놓은 나무의 줄기 원판 (x, y, r) × K, 무대 단위, 표 순서 (= (x, y, r) 순)
	TArray<TWeakObjectPtr<AActor>> Actors;  // 놓은 나무 액터 (Discs 순서)
	TArray<double> GroundZ;                 // 나무마다 밑동 아래 가장 낮은 지면 (cm, 액터 Z = 이 값 − kSinkCm)
	int32 Layout = 0;                       // 표의 그루 수 (0 = 이 무대에는 표가 없다)
	int32 SkippedCover = 0;                 // 은신처 원(반지름 + 2 m) 곁이라 뺀 수 — 은신처가 표가 가정한 자리(무대 1/4·3/4)가 아니거나 레벨 은신처
	int32 SkippedNoGround = 0;              // 줄기 중심 아래 지면을 못 찾아 뺀 수
	int32 SkippedNoMesh = 0;                // 메시를 못 읽었거나 액터를 못 놓은 수
	double MaxReliefCm = 0.0;               // 밑동 아래(중심 + 둘레 6 곳) 지면 높낮이 차 최대 (기울기 기록 — 오르막 쪽은 이만큼 더 묻힌다)

	int32 Num() const { return static_cast<int32>(Discs.size() / 3); }
	/** 표대로 다 놓았나 (빠진 나무가 있으면 파이썬 거울과 원판이 다르다). */
	bool Complete() const { return Num() == Layout; }
};

/**
 * 레벨 나무 이동 검사 (10-18, 무대를 만들 때 한 번 — 기록만, 규칙이 아니다). 줄기 막이마다 팀 이동 제약(EcoCreatureMovement::ConstrainStep, 지역 안·
 * 반경 30 cm 구로 쓸어 봄)을 불러 줄기는 막고 잎 아래는 막지 않는지 본다.
 */
struct ADAPTIVEECOSYSTEM_API FEcoV3TrunkProbe
{
	static constexpr double kRingGapCm = 100.0;   // 잎 아래 둘레 = 줄기 가장자리 + 몸 30 cm + 이만큼 (잎 반경 6~15 m 안)
	static constexpr int32 kRingSteps = 12;       // 둘레 걸음 수 (30° 마다, 한 걸음 = 둘레를 따라 30 cm)

	int32 Trees = 0;           // 잰 줄기 수
	int32 CrossBlocked = 0;    // 줄기를 가로지르는 걸음(줄기 가장자리 + 몸 + 10 cm 밖에서 맞은편까지, 줄기 중심을 지남)이 막힌 수 — 줄기 수와 같아야 한다
	int32 RingSteps = 0;       // 잎 아래 둘레 걸음 수
	int32 RingBlocked = 0;     // 그중 팀 이동 제약이 막은 수 (땅 경사·물·지역 밖 포함)
	int32 RingBlockedByTree = 0;   // 그중 같은 구 쓸기가 우리 나무(EcoV3Tree·EcoV3Trunk 액터)에 닿은 수 — 0 이어야 한다 (잎은 충돌이 없다)
	int32 CrossByTrunk = 0;    // 가로지르기가 막힌 걸음 가운데 같은 구 쓸기가 그 줄기 막이에 닿은 수 — 줄기 수와 같아야 한다
};

/**
 * 사슴 두뇌 행동 몫 (10-18 두뇌 바꾸기 — 기록·화면 전용, 규칙이 아니다). 정의는 R4 보고 도구 herbivore_rl/results/v3/r4/situ_eval.py 와 같다:
 * 산 사슴의 결정 스텝 하나를 그 스텝에 실제로 한 행동(FHerbDecision::ExecutedBehavior)으로 센다. '두뇌 스텝' = 도주 반사(도주·웅크림 덮기)가 덮지
 * 않은 스텝, '늑대를 앎' = 그 스텝의 결정 관측(스텝 앞 기하)에서 pred_count > 0 (깨어 있는 늑대를 보거나 들음).
 */
struct ADAPTIVEECOSYSTEM_API FEcoV3BrainTally
{
	int64 Steps[EcoRepertoireV3::kNumBehaviors] = {};       // 두뇌 스텝 (도주 반사 밖)
	int64 KnowSteps[EcoRepertoireV3::kNumBehaviors] = {};   // 그중 늑대를 앎
	int64 Reflex = 0;                                       // 도주 반사가 덮은 스텝
	int64 ReflexKnow = 0;                                   // 그중 늑대를 앎

	void Add(int32 Behavior, bool bKnows, bool bReflex)
	{
		if (Behavior < 0 || Behavior >= EcoRepertoireV3::kNumBehaviors)
		{
			return;
		}
		if (bReflex)
		{
			++Reflex;
			ReflexKnow += bKnows ? 1 : 0;
			return;
		}
		++Steps[Behavior];
		KnowSteps[Behavior] += bKnows ? 1 : 0;
	}
	int64 Total() const
	{
		int64 N = 0;
		for (const int64 V : Steps)
		{
			N += V;
		}
		return N;
	}
	int64 KnowTotal() const
	{
		int64 N = 0;
		for (const int64 V : KnowSteps)
		{
			N += V;
		}
		return N;
	}
	/** 이 집계 − O (기록 구간). */
	FEcoV3BrainTally Minus(const FEcoV3BrainTally& O) const
	{
		FEcoV3BrainTally D;
		for (int32 b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
		{
			D.Steps[b] = Steps[b] - O.Steps[b];
			D.KnowSteps[b] = KnowSteps[b] - O.KnowSteps[b];
		}
		D.Reflex = Reflex - O.Reflex;
		D.ReflexKnow = ReflexKnow - O.ReflexKnow;
		return D;
	}
};

/** 한 지역의 v3 세계 (무대 하나 = 학습 세계 하나). */
struct ADAPTIVEECOSYSTEM_API FEcoV3RegionContext
{
	FName RegionId;
	int32 RegionRuntimeIndex = INDEX_NONE;
	int32 Index = INDEX_NONE;                 // 컨텍스트 색인 (FEcoIntegratedV3Fragment::ContextIndex)
	EcoWorldV3::FWorldState Sim;
	bool bSpatialFoodRegistered = false;
	int64 ResourceReceiptSequence = 0;
	FVector OriginCm = FVector::ZeroVector;   // 무대 (0, 0) 의 cm. Z = 무대 중심 지면 (기본 높이)
	double SizeUnits = 60.0;
	int32 PlannedDeer = 0;
	int32 PlannedWolves = 0;
	int32 AdoptedDeer = 0;
	int32 AdoptedWolves = 0;
	int32 TeamCovers = 0;                     // v3 원 목록에 넣은 레벨 은신처 (무대 안, 반경이 학습 범위)
	int32 SkippedTeamCovers = 0;              // 무대 안이지만 반경이 학습 범위(4~9 단위) 밖이라 v3 원 목록에서 뺀 레벨 은신처
	int32 ExtraCovers = 0;                    // 우리가 놓은 은신처
	FEcoV3ObstacleScan ObstacleScan;          // 무대 안 세로 장애물 읽기 결과 (야생 2단계 3 — 원판은 Sim.Config.Obstacles 에도 넣는다)
	bool bObstaclesImported = false;          // 원판을 JSON 에서 가져왔다 (eco.IntegratedV3.ObstacleImport — 측정 전용)
	FEcoV3StageTrees Trees;                   // 무대 나무 (eco.IntegratedV3.StageTrees, 10-17 — 원판은 Sim.Config.Obstacles 에도 들어 있다)
	bool bLevelTrees = false;                 // 이 무대에 레벨 나무(줄기 막이, 10-18)가 있다 — 실행 중 나무는 놓지 않는다
	std::vector<double> PlanTrunkDiscs;       // 시작 자리 계획이 피한 레벨 줄기 원판 (GatherLevelTrunks → LevelTrunkDiscs, 무대 단위)
	FEcoV3TrunkProbe TrunkProbe;              // 레벨 나무 이동 검사 (기록만)
	TArray<uint8> ObstacleIsTree;             // 세계 원판마다 무대 나무 줄기인가 (디버그 그리기·기록, Sim.Config.Obstacles 순서. 가져온 원판이면 비어 있다)
	TArray<double> ObstacleGroundZ;           // 원판 중심 지면 높이 (디버그 그리기, Sim.Config.Obstacles 순서)
	TArray<double> CoverGroundZ;              // 은신처 원 중심의 높이 (디버그 그리기)
	TArray<int32> CoverShelterIndices;
	TArray<int64> CoverRegistrations;
	bool bReportedLowDensity = false;         // 학습 밀도 하한 아래 경고를 남겼다

	// 프레임 끝 집계 (처리기가 채운다)
	int32 AliveDeer = 0;
	int32 BehaviorNow[EcoRepertoireV3::kNumBehaviors] = {};
	int32 WolvesNow[static_cast<int32>(EcoV3Integrated::EWolfState::Count)] = {};
	int32 Wolves = 0;

	// 섭식 (먹기 표시·기록). 먹이 단위 = v3 먹이 격자 값 (셀 4 m × 4 m 하나가 많아야 1, 사슴 한 마리는 한 스텝에 많아야 0.06 = 에너지 3%p).
	// 팀 지역 먹이 장부(FRegionEcologyState::FoodAmount)에는 쓰지 않는다 — 팀 재생률이 0 으로 고정이라(EcologyRegion.cpp
	// MakeInitialEcologyState) 한쪽으로만 줄어 거짓 고갈로 보인다
	double StartFood = 0.0;                   // 무대 먹이 처음 합 (= 셀 용량 합, AddContext)
	double MeanEnergy = 0.0;                  // 산 사슴 에너지 평균 (0~1, 결정 스텝마다·프레임 끝)
	int32 StarvingDeer = 0;                   // 산 사슴 중 에너지 kStarvingEnergy 아래
	// 야생 (w1) 지방 비축 (켠 세계만, 결정 스텝마다·프레임 끝. TallyEnergy)
	double MeanReserve = 0.0;                 // 산 사슴 비축 평균 (0~1)
	double MinReserve = 0.0;                  // 산 사슴 비축 최소
	int32 OnReserveDeer = 0;                  // 산 사슴 중 배가 비어(에너지 0) 비축으로 사는 수
	int32 LowReserveDeer = 0;                 // 산 사슴 중 비축 kLowReserve 아래
	int32 WeakDeer = 0;                       // 산 사슴 중 배 WeakE 밑 (느림)
	int32 AteDeerInterval = 0;                // 이번 기록 구간에 한 번이라도 먹은 사슴 (그 뒤 죽은 사슴 포함)
	int32 LogEpoch = 0;                       // 기록 구간 번호 (LogContext 마다 + 1)
	TArray<double> RecentEaten;               // 최근 kRecentEatSteps 결정 스텝의 스텝마다 먹은 양 (고리 버퍼)
	int32 RecentEatenPos = 0;
	double LastStepFoodEaten = 0.0;           // 지난 결정 스텝 끝의 Sim.Stats.FoodEaten (스텝 차이 계산)

	/** 결정 스텝 하나 끝: 이번 스텝 먹은 양을 고리 버퍼에 넣는다. */
	void PushStepEaten()
	{
		if (RecentEaten.Num() != EcoV3Integrated::kRecentEatSteps)
		{
			RecentEaten.Init(0.0, EcoV3Integrated::kRecentEatSteps);
			RecentEatenPos = 0;
		}
		RecentEaten[RecentEatenPos] = Sim.Stats.FoodEaten - LastStepFoodEaten;
		RecentEatenPos = (RecentEatenPos + 1) % EcoV3Integrated::kRecentEatSteps;
		LastStepFoodEaten = Sim.Stats.FoodEaten;
	}
	/** 최근 10 초(결정 스텝 75 개) 먹은 양 (먹이 단위). */
	double RecentEatenSum() const
	{
		double Sum = 0.0;
		for (const double V : RecentEaten)
		{
			Sum += V;
		}
		return Sum;
	}
	/** 무대 먹이 지금 합 ÷ 처음 합 (0~1). */
	double FoodFraction() const
	{
		return StartFood > 0.0 ? Sim.Food.Total() / StartFood : 0.0;
	}

	// 늑대 밤잠 점진화 기록 (해 진·뜬 시각 — 잠듦·깸 줄의 '해 진 뒤 초'). -1 = 아직 모른다
	int64 DarkStartT = -1;                    // 마지막으로 어둠(d ≥ 0.5)이 시작된 전역 스텝
	int64 LightStartT = -1;                   // 마지막으로 밝아진(d < 0.5) 전역 스텝
	bool bPrevDark = false;                   // 지난 결정 스텝 끝의 어둠 (d ≥ 0.5)
	bool bDarkKnown = false;                  // bPrevDark 가 정해졌다

	// 사슴 얼기 막음·늑대 식사 기록 (사람 결정 10-15 (A)(B), 처리기가 결정 스텝마다 채운다)
	int64 FreezeMaskOpen = 0;                 // 요청을 읽은 결정 중 마스크에 얼기 칸이 열린 수 (얼기를 막으면 늘 0)
	int64 LastLogFreezeMaskOpen = 0;
	FEcoV3WolfEatTally Eat;
	FEcoV3WolfEatTally LastLogEat;
	TMap<int64, int32> WolfCatchesById;       // 늑대 StableAgentId → 포획 누적 (기록 줄 '늑대별 포획')
	TMap<int64, int64> WolfLastCatchStep;     // 늑대 StableAgentId → 마지막으로 잡은 스텝 번호 (이어 사냥 판정)

	// 경계 거리 기록 (사람 결정 10-15 (C), 처리기가 채운다. 규칙 켬·끔 모두 센다)
	int64 NearEatingDeerSteps = 0;            // 식사 중(쿨다운 > 0)인 깨어 있는 늑대의 15 m 안에 있던 산 사슴 (개체·스텝, 스텝 끝)
	int64 LastLogNearEatingDeerSteps = 0;
	int32 KeepNow[EcoWorldV3::kNumKeepModes] = {};   // 프레임 끝 산 사슴의 덮기 (화면 집계)

	// 두뇌 행동 몫 (10-18 두뇌 바꾸기, 처리기가 결정 스텝마다 채운다 — FEcoV3BrainTally)
	FEcoV3BrainTally BrainTally;              // 누적 (Play 시작부터)
	FEcoV3BrainTally LastLogBrainTally;       // 지난 기록 줄의 누적
	FEcoV3BrainTally SinceSwapBrainTally;     // 지금 두뇌로 바뀐 뒤 (화면 '늑대를 알 때 숨기')

	// R5 장애물 관측 대조 기록 (10-19, eco.IntegratedV3.ObsParityLog — LogObsParity)
	bool bObsParityDiscsLogged = false;       // 이 무대의 원판 줄을 남겼다
	int64 ObsParityLines = 0;                 // 남긴 사슴 줄 수
	uint64 ObsParityDecisionHash = 14695981039346656037ULL;   // 결정 지문 (FNV-1a 64 — 스텝마다 사슴마다 id·읽음·마스크·요청·로짓 비트·실행 행동, 시작부터 누적)
	int64 ObsParityDecisions = 0;             // 그 지문에 넣은 사슴·스텝 수

	/**
	 * 늑대 하나의 결정 스텝 하나를 센다 (처리기가 Step 뒤에 부른다. StepIndex = 이번 스텝 번호 = Step 뒤 Sim.T − 1).
	 * 돌진 시작이면 앞 포획 뒤 경과로 이어 사냥·식사 끝 3 초 안을 가르고, 식사 중(잡지 않았고 쿨다운 > 0)이면 움직였는지 보고,
	 * 잡았으면 포획·늑대별 포획·앞 포획 뒤 경과를 센 뒤 마지막 포획 스텝을 바꾼다.
	 */
	void TallyWolfStep(const EcoWorldV3::FThreatAgent& A, int64 WolfId, int64 StepIndex);

	// 기록
	int64 TerrainChecks = 0;                  // 지형 제약으로 검사한 이동 수 (콜백이 실제로 도는지 보는 기록)
	int64 LastLogTerrainChecks = 0;
	int64 LastLogT = 0;
	EcoWorldV3::FWorldStats LastLogStats;
	TArray<FEcoV3IntegratedCatchMark> RecentCatches;

	FVector UnitsToCm(double X, double Y, double Z) const
	{
		return FVector(OriginCm.X + X * EcoRepertoireV3::kUnitCm, OriginCm.Y + Y * EcoRepertoireV3::kUnitCm, Z);
	}
	EcoWorldV3::FVec2 CmToUnits(const FVector& P) const
	{
		return {(P.X - OriginCm.X) / EcoRepertoireV3::kUnitCm, (P.Y - OriginCm.Y) / EcoRepertoireV3::kUnitCm};
	}
	double SizeCm() const { return SizeUnits * EcoRepertoireV3::kUnitCm; }
};

/**
 * 서식지 스트리밍 조정자의 시작 직전 지면 검사 틱. TG_LastDemotable 은 엔진 스트리밍 갱신(UWorld::Tick 의 InternalUpdateStreamingState)
 * 뒤이고 조정자의 OnWorldPostActorTick(StartAuthority) 앞이다 — 그 사이에는 스트리밍 상태가 바뀌지 않는다.
 */
struct FEcoV3PreStartTickFunction : public FTickFunction
{
	TWeakObjectPtr<UEcoPolicyV3IntegratedSubsystem> Owner;

	virtual void ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
							 const FGraphEventRef& MyCompletionGraphEvent) override;
	virtual FString DiagnosticMessage() override { return TEXT("EcoV3I 시작 직전 지면 검사"); }
	virtual FName DiagnosticContext(bool bDetailed) override { return FName(TEXT("EcoV3IPreStart")); }
};

/** 조정자에서 우리가 바꾸는 공개 속성의 팀 값 (시작 직전 검사가 실패하면 되돌린다). */
struct FEcoV3SpawnerTeamValues
{
	TArray<FEcoCreatureSpawnGroup> Groups;
	FEcoMigrationSettings Migration;
	bool bEnableWaves = false;
	float EnergyDrainPerSecond = 0.0f;
	float EnergyPerFood = 0.0f;
	double DaySeconds = 60.0;
	double NightSeconds = 60.0;
	int32 GlobalPopulationLimit = 0;
	bool bValid = false;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3IntegratedSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** 스위치: 콘솔 변수 eco.IntegratedPolicyVersion 이 3 이면 3, 그 밖은 1 (끔). 명령줄 -EcoIntegratedV3 는 그 콘솔 변수의 시작값이다. */
	static int32 GetRequestedVersion();
	static bool IsRequested() { return GetRequestedVersion() == 3; }
	/** 콘솔 변수 eco.V3Debug (명령줄 -EcoV3Debug 는 시작값). */
	static bool IsDebugDrawEnabled();

	/**
	 * 명령줄 인자 → 콘솔 변수 시작값. ECVF_SetByCommandline 우선순위로만 쓰고, 콘솔·코드가 이미 정한 변수는 건드리지 않는다
	 * (그래서 콘솔에서 끄면 명령줄이 다시 켜지 않는다). 처음 스위치를 읽을 때 진짜 명령줄로 한 번 부른다. 시험은 문자열을 넘긴다.
	 */
	static void ApplyCommandLineToConsole(const TCHAR* CmdLine);

	/**
	 * 서식지 스트리밍 조정자가 이 프레임 끝에 StartAuthority 를 부르는가 (조정자 Tick 과 같은 조건: BeginPlay 뒤 30 초를 넘으면 시간 초과,
	 * 0.25 초 미만이거나 스트리밍 원천이 덜 끝났으면 기다림).
	 */
	static bool CoordinatorStartsThisFrame(double SecondsSinceBeginPlay, bool bStreamingCompleted)
	{
		return SecondsSinceBeginPlay >= 0.25 && SecondsSinceBeginPlay <= 30.0 && bStreamingCompleted;
	}

	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

	bool IsActive() const { return bActive; }
	/** Quiesce the native writer after a rejected authority resource transaction. */
	void RejectResourceContract();
	bool UsesTerrain() const { return bUseTerrain; }
	const FEcoV3IntegratedSettings& GetSettings() const { return Settings; }

	// ---- 계획 (엔진 상태 없이 시험할 수 있게 함수만 받는다) ----

	/**
	 * 한 지역 무대와 시작 자리. Contains = 지역 상자 안인가, Project = 지면 검사(성공하면 지면 점).
	 * bRequireGround 면 지면 검사를 통과한 점만 쓴다 (못 채우면 false). 아니면 검사에 실패한 점도 힌트로 쓴다(스트리밍 전 계획).
	 * 시작 자리 난수는 (세션 시드, 그룹 번호) 로 정해진다 — 같은 입력이면 같은 자리.
	 * 무대 나무 (S.bStageTrees ∧ S.bObstacles, 10-17): 그 지역 표의 줄기 원판(반지름 + 몸 0.15 단위) 안 자리는 버리고 다음 자리를 뽑는다 — 세계 원판 안
	 * 판정(EcoThreatV3::InsideAnyObstacle)과 같은 식이라 입양 때 원판 밖 밀어내기(ObstaclePushOut)가 할 일이 없다. 표가 없는 지역·크기는 그대로다.
	 * 레벨 나무 (10-18): LevelTrunksCm(GatherLevelTrunks — 세계 cm 의 줄기 막이 원판)를 주고 S.bObstacles 면, 그 가운데 이 무대 안 줄기(LevelTrunkDiscs —
	 * 세계에 넣을 원판과 같은 값)를 피한다. 무대 안에 레벨 줄기가 하나라도 있으면 표(실행 중 나무)는 쓰지 않는다 — 그 무대에는 실행 중 나무를 놓지 않는다.
	 * 피한 원판은 Out.TrunkDiscs (무대 단위), 레벨 줄기였으면 Out.bLevelTrunks.
	 */
	static bool PlanStage(FName RegionId, int32 GroupIndex, const FVector& DesiredCenterCm, const FVector& RegionCenterCm,
						  const FEcoV3IntegratedSettings& S, int32 NumDeer, int32 NumWolves, bool bRequireGround,
						  TFunctionRef<bool(const FVector&)> Contains, TFunctionRef<bool(const FVector&, FVector&)> Project,
						  FEcoV3StagePlan& Out, const TArray<FVector>* LevelTrunksCm = nullptr);
	/**
	 * 무대 중심 (PlanStage 와 같은 규칙): 바라는 중심에서 네 모서리가 지역 상자 안이면 그대로, 아니면 지역 중심 쪽으로 1/20 씩 옮겨 처음 드는 곳.
	 * 끝내 안 들면 바라는 중심 그대로 (bOutInside 거짓). 레벨 나무 놓기 명령(EcoV3PlaceTreesCommandlet)도 이 함수로 무대 자리를 찾는다.
	 */
	static FVector StageCenterCm(const FVector& DesiredCenterCm, const FVector& RegionCenterCm, double SizeUnits,
								 TFunctionRef<bool(const FVector&)> Contains, bool& bOutInside);

	/**
	 * 무대 안 세로 장애물 읽기 (야생 2단계 3, 레벨을 읽기만 한다). OriginCm = 무대 (0, 0) 의 cm, SizeUnits = 무대 한 변, Covers = 은신처 원(무대 단위 —
	 * 중심이 원 안인 메시는 빼고), Exclude = 뺄 액터(우리가 놓은 은신처). bProbeGround 면 2 m 격자로 지면 경사·물을 세어 기록한다(원판에는 넣지 않는다).
	 * LayoutRegion (10-18): 지역 이름을 주면 레벨 나무 줄기 막이(꼬리표 EcoV3Trunk) 원판을 그 지역 배치 표와 맞춘다(SnapToLayout — 1 cm 안이면 표 값).
	 */
	static void ScanStageObstacles(UWorld& World, const FVector& OriginCm, double SizeUnits, const std::vector<EcoObservationV3::FCoverInput>& Covers,
								   const TSet<const AActor*>& Exclude, bool bProbeGround, FEcoV3ObstacleScan& Out, FName LayoutRegion = NAME_None);
	/** 지역마다 세계가 쓰는 원판 목록(레벨에서 읽었거나 가져온 원판)과 읽기 기록을 JSON 으로 쓴다 (파이썬 거울 run_mirror.py --unreal-obstacles 가 읽는다). 성공하면 참. */
	bool ExportObstacles(const FString& Path) const;
	/** 원판 JSON(ExportObstacles·results/v3/wild2/make_obstacle_maps.py 꼴)을 읽는다: 지역 이름 → (x, y, r) × K. 반지름 0 이하는 뺀다. 못 읽으면 거짓. */
	static bool LoadObstacleImport(const FString& Path, TMap<FName, std::vector<double>>& Out);

	// ---- 환경 스냅숏 (10-18 적응 고리, EcoV3Snapshot.cpp — 명세 Docs/RL_Policy/SEASON_SNAPSHOT_SPEC.md 11절) ----

	/**
	 * 지금 세계 스냅숏 JSON (eco_v3_snapshot 판 1)을 Path 에 쓴다 — 파이썬 herbivore_rl/results/v3/adapt/adapt.py 가 이 파일로 거울 세계를 다시 짓는다.
	 * 담는 것: 세션 시드·전역 스텝·지금 두뇌·계약 해시·통합 설정 스위치, 지역마다 무대 자리·세계 설정 값·허용 칸·은신처 원·장애물 원판(레벨 나무 포함)·
	 * 먹이 격자(용량·지금 먹이, 행 우선)·날씨(설정·지금)·사슴·늑대 수와 누적 잡힘·굶음·사냥. 읽기만 한다 (세계를 바꾸지 않는다). Why = 기록용 까닭. 성공하면 참.
	 */
	bool ExportSnapshot(const FString& Path, const FString& Why) const;
	/**
	 * 스냅숏 경로. Out 이 비면 <프로젝트>/Saved/EcoSnapshots/eco_v3_snapshot_s<세션 시드>_t<전역 스텝>.json, '.json' 으로 끝나면 그 파일
	 * (상대 경로는 프로젝트 폴더 기준), 아니면 그 폴더 안의 같은 이름.
	 */
	FString SnapshotPath(const FString& Out) const;
	/**
	 * 예정 스냅숏 (eco.IntegratedV3.SnapshotAt 초 ≥ 0 — 명령줄 -EcoV3SnapshotAt=): 전역 스텝 × 2/15 초가 그 시각 이상인 첫 결정 스텝 경계에서 한 번
	 * eco.IntegratedV3.SnapshotOut 경로에 쓴다. 처리기가 SyncBrain 곁(스텝 앞)에서 부른다 — 그 시각까지 모든 지역이 같은 수의 스텝을 마친 상태다.
	 */
	void MaybeScheduledSnapshot();

	// ---- 무대 나무 (10-17, 배치 표 TreeLayoutV3.h — 파이썬 make_tree_layout.py) ----

	/** 그 지역 무대의 나무 표 (지역 이름이 같고 무대 한 변이 표의 한 변과 같을 때만, 아니면 nullptr). 표가 있어도 그루 수가 0 일 수 있다(메마른 땅). */
	static const EcoTreeLayoutV3::FStageTrees* FindStageTrees(FName RegionId, double SizeUnits);
	/** 표의 줄기 원판 (x, y, r) × K (무대 단위, 표 순서 = (x, y, r) 순). 표가 없으면 빈 목록. */
	static std::vector<double> StageTreeDiscs(FName RegionId, double SizeUnits);
	/**
	 * 실행 중 나무 놓기 (레벨·메시 애셋은 바꾸지 않는다). 표 나무마다 줄기 중심·둘레 6 곳(줄기 반지름)의 지면을 아래로 선 검사(ECC_WorldStatic,
	 * 팀 ProjectSpawnPoint 와 같은 길이)해 가장 낮은 지면 − kSinkCm 에 액터 기준점을 둔다. 액터 = AStaticMeshActor(움직임 가능 — 실행 중 메시를 넣으려고,
	 * 충돌 없음, 그림자 켬, 꼬리표 EcoV3StageTree). Avoid = 피할 원(무대 단위 — 은신처) — 줄기 가장자리가 반지름 + 2 m 안이면 그 나무는 뺀다.
	 */
	static void SpawnStageTrees(UWorld& World, FName RegionId, const FVector& OriginCm, double SizeUnits,
								const std::vector<EcoObservationV3::FCoverInput>& Avoid, FEcoV3StageTrees& Out);
	/**
	 * 레벨 읽기 원판과 나무 원판을 합쳐 (x, 다음 y, 다음 r) 순으로 늘어놓는다 (ScanStageObstacles 와 같은 순서). OutIsTree = 원판마다 나무에서 왔나
	 * (LevelIsTree = 레벨 원판마다 레벨 나무 줄기인가 — 주면 그 원판도 나무로 적는다).
	 */
	static std::vector<double> MergeDiscs(const std::vector<double>& Level, const std::vector<double>& Trees, TArray<uint8>* OutIsTree = nullptr,
										  const TArray<uint8>* LevelIsTree = nullptr);
	/**
	 * 나무 하나의 지면 (SpawnStageTrees 와 같은 검사): 줄기 중심 + 둘레 6 곳(줄기 반지름, 60° 간격)을 위에서 아래로 선 검사(ECC_WorldStatic, OriginCm.Z
	 * + 50 m → − 200 m)해 가장 낮은·높은 지면. 줄기 중심에서 지면을 못 찾으면 거짓. Ignore = 검사에서 뺄 액터 (레벨 나무를 다시 놓을 때 그 나무 자신).
	 */
	static bool GroundStageTree(UWorld& World, const FVector& OriginCm, const EcoTreeLayoutV3::FTree& T, double& OutMinZ, double& OutMaxZ,
								const TArray<AActor*>* Ignore = nullptr);

	// ---- 레벨 나무 (10-18 — 통합 레벨에 놓은 나무 액터·줄기 막이, EcoV3PlaceTreesCommandlet) ----

	static FName LevelTreeTag();    // 나무 액터 (팀 Beech_Tree, 충돌 없음) 꼬리표 'EcoV3Tree'
	static FName LevelTrunkTag();   // 줄기 막이 (엔진 원기둥, 게임에서 숨김, BlockAll) 꼬리표 'EcoV3Trunk'
	static const TCHAR* LevelTreeFolder();      // 월드 아웃라이너 폴더 'EcoV3_Trees'
	static const TCHAR* LevelTrunkMeshPath();   // 줄기 막이 메시 '/Engine/BasicShapes/Cylinder.Cylinder'
	static constexpr double kLevelTrunkSinkCm = 30.0;    // 줄기 막이 밑면 = 밑동 아래 가장 낮은 땅 − 이만큼
	static constexpr double kLevelTrunkTopCm = 400.0;    // 줄기 막이 윗면 = 밑동 아래 가장 낮은 땅 + 이만큼 (팀 이동 제약 구 높이 65 + 30 cm 위)
	static constexpr double kLevelTreeSnapCm = 1.0;      // 레벨 줄기 원판이 표 원판과 중심·반지름 모두 이만큼 안이면 표 값을 쓴다

	/** 나무 액터 변환 (SpawnStageTrees 와 같다): 기준점 (PivotX, PivotY), Z = 가장 낮은 지면 − kSinkCm, 방위 YawDeg, 크기 Scale. */
	static FTransform LevelTreeTransform(const EcoTreeLayoutV3::FTree& T, const FVector& OriginCm, double GroundMinZ);
	/**
	 * 줄기 막이 변환: Cylinder 의 충돌 상자(레벨 읽기와 같은 상자)가 가로 반폭 평균 = 줄기 원판 반지름 R, 가로 중심 = 줄기 중심 (X, Y), 밑면 = 가장 낮은
	 * 지면 − kLevelTrunkSinkCm, 윗면 = + kLevelTrunkTopCm 이 되게 (방위 0). 메시 충돌 상자가 비었으면 거짓.
	 */
	static bool LevelTrunkTransform(const EcoTreeLayoutV3::FTree& T, const FVector& OriginCm, double GroundMinZ, const UStaticMesh& Cylinder,
									FTransform& Out);
	/** 세계의 레벨 줄기 막이 원판 (cm: X, Y = 충돌 상자 가로 중심, Z = 반지름) — 레벨 읽기가 원판으로 넣는 조건(충돌·반지름·높이)을 통과한 것만. */
	static void GatherLevelTrunks(UWorld& World, TArray<FVector>& OutCm);
	/** 그중 이 무대 안 줄기 (무대 단위, 레벨 읽기와 같은 셈 + SnapToLayout, (x, y, r) 순). OutSnapped = 표 값으로 바꾼 수. */
	static std::vector<double> LevelTrunkDiscs(const TArray<FVector>& TrunksCm, FName RegionId, const FVector& OriginCm, double SizeUnits,
											   int32* OutSnapped = nullptr);
	/**
	 * 줄기 원판 (무대 단위) 하나를 그 지역 배치 표와 맞춘다: 표 줄기 가운데 중심·반지름 차이가 모두 kLevelTreeSnapCm 안인 것이 있으면 그 표 값으로 바꾸고
	 * 참 (OutDevCm = 바꾸기 전 차이 최대, cm). 표가 없거나 맞는 줄기가 없으면 그대로 두고 거짓.
	 */
	static bool SnapToLayout(FName RegionId, double SizeUnits, double& X, double& Y, double& R, double* OutDevCm = nullptr);
	/** 레벨 나무 이동 검사 (FEcoV3TrunkProbe): 무대 안 줄기 막이마다 팀 이동 제약으로 가로지르기·잎 아래 둘레 걸음을 쓸어 본다. */
	static void ProbeLevelTrunks(UWorld& World, FName RegionId, const FVector& OriginCm, double SizeUnits, FEcoV3TrunkProbe& Out);

	/** 지역 v3 세계 설정 (무대 한 변·늑대 구성·낮밤 900·통합 모드 칸). Covers 는 무대 단위. RegionId = 지역 날씨를 고르는 이름 (S.WeatherFor — 없으면 맑음). */
	static EcoWorldV3::FWorldConfig MakeRegionWorldConfig(const FEcoV3IntegratedSettings& S, int32 RegionRuntimeIndex,
														  int32 PlannedDeer, int32 PlannedWolves,
														  const std::vector<EcoObservationV3::FCoverInput>& Covers, FName RegionId = NAME_None);

	// ---- 처리기 쪽 ----

	/** 프레임 dt → 이번 프레임에 돌 전역 결정 스텝 수 (최대 64). 평면 시험 경로의 시계와 따로다. */
	int32 AdvanceClock(float DeltaSeconds);
	float GetVisualAlpha() const;
	int64 GetGlobalStep() const { return GlobalT; }
	/** 모든 컨텍스트가 결정 스텝 하나를 마쳤다 → 전역 t + 1. */
	void FinishGlobalStep() { ++GlobalT; }
	/** 컨텍스트의 t 를 전역 t 에 맞춘다 (어둠 다시 계산). */
	void SyncContextClock(FEcoV3RegionContext& Ctx) const;

	int32 NumContexts() const { return Contexts.Num(); }
	/** Synchronize static authored refuge removal without reindexing policy cover targets. */
	void RefreshRefuges(FEcoV3RegionContext& Context);
	FEcoV3RegionContext* GetContext(int32 Index) { return Contexts.IsValidIndex(Index) ? Contexts[Index].Get() : nullptr; }
	const FEcoV3RegionContext* GetContext(int32 Index) const { return Contexts.IsValidIndex(Index) ? Contexts[Index].Get() : nullptr; }
	FEcoV3RegionContext* FindContext(FName RegionId);

	/** 처리기가 한 컨텍스트의 결정 스텝 하나를 마칠 때마다 부른다 (포획 표시·기록). */
	void NotifyContextStep(FEcoV3RegionContext& Ctx, const EcoWorldV3::FStepReport& Report);
	/**
	 * 늑대 밤잠 점진화 기록 (처리기가 결정 스텝 하나 뒤, NotifyContextStep 앞에 부른다): 해 진·뜬 시각을 갱신하고 늑대마다 이번 스텝의
	 * 밤잠 사건(잠듦·깸·눕기 시작·다시 일어남)을 한 줄씩 남긴다. 가장 가까운 사슴은 이번 스텝 이동 뒤 산 사슴(Sim.Prey)이다.
	 * Threats·WolfIds 는 이번 Step 배열과 같은 순서다. 밤잠 점진화를 끈 세계는 아무것도 하지 않는다.
	 */
	void NotifyNightStep(FEcoV3RegionContext& Ctx, EcoWorldV3::FThreatAgent* const* Threats, const int64* WolfIds, int32 NumWolves);
	/** [EcoV3I] 기록 줄을 지금 남긴다. */
	void LogContext(FEcoV3RegionContext& Ctx);
	// ---- 두뇌 (10-18 실행 중 가중치 로더 — EcoV3Brain.h) ----

	/**
	 * 결정 스텝 경계 (처리기가 Execute 머리(bPollWatch 참)와 전역 스텝마다 부른다): 예정 바꾸기(eco.V3Brain.SwapAtSeconds — 전역 스텝 × 2/15 초가 그 시각
	 * 이상인 첫 경계)·폴더 감시를 보고, 저장소의 대기 두뇌를 지금 두뇌로 바꾸고, 바뀌었으면 모든 지역 세계의 허용 칸을 새 두뇌 ∧ 세계 칸으로 다시 정하고
	 * '[EcoV3I] 두뇌 바꿈' 한 줄을 남긴다 (처음 한 번은 '[EcoV3I] 두뇌 시작'). 사슴 몸·행동 상태·요청은 건드리지 않는다.
	 */
	void SyncBrain(bool bPollWatch);
	/** 이 월드가 지금 쓰는 두뇌 (SyncBrain 전에는 저장소의 지금 두뇌). */
	const FEcoV3Brain& GetActiveBrain() const;
	const EcoPolicyV3::FPolicyNetV3& ActiveNet() const { return GetActiveBrain().Net; }
	/** 마지막으로 두뇌를 바꾼 전역 스텝 (이 Play 에서 바꾼 적이 없으면 -1). 그 스텝부터의 결정은 새 두뇌다. */
	int64 GetLastBrainSwapStep() const { return LastBrainSwapStep; }

	// ---- R5 장애물 관측 대조 기록 (10-19, 계약 2-4) ----

	/** eco.IntegratedV3.ObsParityLog (전역 스텝 간격, 0 = 끔). 켜면 관측 18 두뇌여도 세계가 장애물 세 칸을 만든다 (EcoWorldV3::FWorldState::bObstacleObsProbe — 결정은 그대로). */
	static int32 ObsParityEvery();
	/**
	 * 처리기가 한 지역의 결정 스텝 하나 뒤에 부른다 (ObsParityEvery 가 0 이면 아무것도 안 한다). 전역 스텝이 그 간격의 배수면 산 사슴마다 '[EcoV3Obs]' 한 줄
	 * (자리·heading·위협을 앎·away·가장 가까운 위협 자리 → E·N·가림·관측 세 칸 float 비트)과 결정 지문 줄(시작부터 스텝마다 사슴마다 id·읽음·마스크·요청·
	 * 로짓 비트·실행 행동의 FNV-1a 64 — 두 판의 모든 결정이 같은지 본다)을, 지역마다 처음 한 번 원판 줄을 남긴다. 파이썬
	 * herbivore_rl/results/v3/r5/unreal_parity.py 가 같은 입력으로 world.obstacle_obs_values 를 다시 돌려 비트 단위로 견준다. Views·Ids 는 이번 Step 배열 순서다.
	 */
	void LogObsParity(FEcoV3RegionContext& Ctx, const EcoWorldV3::FHerbView* Views, const int64* Ids, int32 Num);

	/** 처리기가 한 프레임에 결정 스텝 Steps 개(모든 지역)를 돈 시간 (기록 줄의 '결정 스텝 CPU'). */
	void AddStepCpuSeconds(double Seconds, int32 Steps)
	{
		StepCpuSeconds += Seconds;
		StepCpuSteps += Steps;
		StepCpuMaxFrameSeconds = FMath::Max(StepCpuMaxFrameSeconds, Seconds);
	}

	/**
	 * 지형 제약 이동 검사: FromCm → ToCm 를 30 cm 이하 토막으로 나눠 팀 공개 함수 EcoCreatureMovement::ConstrainStep (지역 안·장애물·
	 * 지면·물) 을 부른다. 통과하면 OutZ = 끝 지면 높이, 막히면 거짓 (OutZ = FromCm.Z).
	 */
	bool TraceMove(FName RegionId, const FVector& FromCm, const FVector& ToCm, double& OutZ) const;

	// ---- 시험·조정자 없이 쓰는 길 ----

	/** 조정자 없이 켠다 (자동화 시험). bTerrain 이 거짓이면 지형 제약 콜백을 쓰지 않는다. */
	void ActivateForTest(const FEcoV3IntegratedSettings& InSettings, bool bTerrain);
	/** 컨텍스트 하나를 만든다 (t = 전역 t). 반환 포인터는 서브시스템이 끝날 때까지 유효하다. */
	FEcoV3RegionContext* AddContext(FName RegionId, int32 RegionRuntimeIndex, const FVector& OriginCm,
									const EcoWorldV3::FWorldConfig& Config, int32 PlannedDeer, int32 PlannedWolves);
	/** 시험: OnWorldBeginPlay 의 조정자 바꾸기만 (넷 모드·스위치 검사 없이). 성공하면 켜진 상태가 된다 (틱·델리게이트는 등록하지 않는다). */
	bool ApplyToSpawnerForTest(AEcoCreatureIntegrationSpawner& InSpawner, const FEcoV3IntegratedSettings& InSettings);
	/** 시험: 시작 직전 지면 검사를 지금 한 번 (실패하면 팀 값으로 되돌리고 끈다). */
	bool ValidateSpawnPointsForTest() { return ValidateSpawnPointsNow(); }
	/** 팀 늑대 표현 액터의 동작을 센다 (읽기만. 프레임마다 HandlePreActorTick 이 부르고, 시험도 부른다): 식사 깃발이 선 늑대가 '먹는 중' 동작인가. */
	void TallyTeamWolfVisuals();
	const TArray<FEcoV3StagePlan>& GetPlans() const { return Plans; }

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	friend struct FEcoV3PreStartTickFunction;

	bool ApplyToSpawner(AEcoCreatureIntegrationSpawner& InSpawner);
	/** 시작 직전 지면 검사 (스트리밍 조정자). 실패하면 RestoreTeamValues + 끔. */
	bool ValidateSpawnPointsNow();
	void RestoreTeamValues(const TCHAR* Why);
	void Deactivate(const TCHAR* Why);
	void HandlePreActorTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds);
	void HandlePreStartTick();
	void TryCreateContexts();
	void CheckClockDrift();
	void DrawOverlay();
	/**
	 * 보기 환경 (Play 동안만, 끝나면 되돌린다).
	 * - 엔진은 한 액터에 디버그 글자를 128개까지만 그린다(r.DebugSafeZone.MaxDebugTextStringsPerActor). 우리 글자는 모두 WorldSettings 에
	 *   붙으므로 eco.V3Debug 를 켠 동안만 한도를 푼다(0 = 한도 없음). 그릴 수 없는 실행(-NullRHI)에서는 풀지 않는다 — HUD 가 그려지지
	 *   않아 엔진이 글자 목록을 비우지 않으므로, 한도가 없으면 목록이 끝없이 늘어 프레임이 점점 느려진다.
	 * - 팀 이주 디버그 글자('ID n Forest Resident')는 v3 모드에서 이주를 꺼 두므로 뜻이 없고 행동 글자를 가린다. v3 모드 동안만
	 *   UEcoRuntimeSettings 기본 객체의 bDrawMigrationDebug 를 끈다. 설정 파일에는 쓰지 않는다.
	 */
	void UpdateViewEnvironment();
	void RestoreViewEnvironment();

	TWeakObjectPtr<AEcoCreatureIntegrationSpawner> Spawner;
	TArray<FEcoV3StagePlan> Plans;
	TArray<TUniquePtr<FEcoV3RegionContext>> Contexts;
	TArray<TWeakObjectPtr<AActor>> SpawnedCovers;
	TArray<TWeakObjectPtr<AActor>> SpawnedTrees;   // 무대 나무 액터 (eco.IntegratedV3.StageTrees — 레벨 읽기에서 뺀다)
	TSet<int32> OurShelterIndices;            // 우리가 놓은 앵커의 UEcoShelterSubsystem RuntimeIndex (레벨 은신처와 가른다)
	FEcoV3IntegratedSettings Settings;

	/** 팀 값 (되돌리기용). 설정 에셋은 GC 가 보도록 UPROPERTY 로 쥔다 — 조정자는 바꾼 뒤 우리 설정만 가리킨다. */
	FEcoV3SpawnerTeamValues TeamValues;
	UPROPERTY(Transient)
	TObjectPtr<UMassEntityConfigAsset> TeamHerbivoreConfig;
	UPROPERTY(Transient)
	TObjectPtr<UMassEntityConfigAsset> TeamWolfConfig;

	FEcoV3PreStartTickFunction PreStartTick;

	bool bActive = false;
	bool bUseTerrain = true;
	bool bStreamingSpawner = false;   // 조정자가 서식지 스트리밍을 기다린 뒤 시작한다 (시작 직전 지면 검사가 필요하다)
	bool bPointsFinal = false;        // 시작 자리를 더 검사하지 않는다
	bool bContextsCreated = false;

	double BeginPlaySeconds = 0.0;    // OnWorldBeginPlay 시각 = 조정자 BeginPlay 의 StartedAt (같은 UWorld::BeginPlay 안이라 시각이 같다)
	int32 ValidationPasses = 0;       // 시작 직전 지면 검사 횟수 (많아야 kMaxValidationPasses)

	int64 GlobalT = 0;
	EcoPolicy::FStepClock Clock;
	int32 ClockPhase = 0;
	int32 LogEverySteps = 75;

	double StepCpuSeconds = 0.0;          // 시작부터 결정 스텝(모든 지역) 누적 시간
	int64 StepCpuSteps = 0;
	double StepCpuMaxFrameSeconds = 0.0;  // 한 프레임의 결정 스텝 시간 최댓값 (스텝이 몰린 프레임의 끊김)

	// 두뇌 (SyncBrain)
	FEcoV3BrainPtr ActiveBrain;           // 이 월드가 지금 쓰는 두뇌 (첫 SyncBrain 전에는 비어 있다)
	uint32 AppliedBrainGen = 0;           // 지역 세계 허용 칸에 반영한 저장소 세대 (0 = 아직)
	bool bScheduledSwapDone = false;      // 이 Play 의 예정 바꾸기를 했다 (성공·거부 모두 한 번만)
	int64 LastBrainSwapStep = -1;
	FString LastBrainSwapFrom;            // 마지막으로 바꾸기 전 두뇌 id (기록 줄 '구간 중 바꿈')
	bool bScheduledSnapshotDone = false;  // 이 Play 의 예정 스냅숏을 했다 (성공·실패 모두 한 번만)

	FDelegateHandle PreTickHandle;

	bool bTextLimitRaised = false;
	int32 SavedTextLimit = 128;
	bool bMigrationDebugHidden = false;
	bool bSavedMigrationDebug = true;
	double NextScreenTally = 0.0;
};
