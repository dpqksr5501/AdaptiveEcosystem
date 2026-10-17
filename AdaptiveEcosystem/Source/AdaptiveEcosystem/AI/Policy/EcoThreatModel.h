// v3 위협 모델 — 파이썬 학습 세계의 위협(늑대·잠행형·플레이어 대역) 한 마리의 결정 스텝 하나를 C++ 로 옮긴다.
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.**
// `<cmath>`·`<cstdint>` 만 쓴다(EcoPolicyV3Inference.h 와 같은 이유). 엔진 없이 g++ 로 골든을 대조할 수 있고
// (herbivore_rl/tests/test_threat_golden_v3.py), 같은 파일이 UE 자동화 시험(Tests/EcoThreatModelV3Test.cpp)에서도 그대로 돈다.
// UObject·Mass 와 무관한 순수 함수뿐이다. 언리얼의 uint8·int32 는 std::uint8_t·std::int32_t 와 같은 타입이다.
//
// 원칙: 언리얼 세계는 학습 세계의 부분집합이다(계약 Docs/RL_Policy/POLICY_CONTRACT_V3.md 7-7). 게임의 사슴 두뇌 R1b 는
// configs/v3_r1_on.yaml 세계에서 배웠으므로, 언리얼 늑대도 그 세계의 위협 규칙을 그대로 따라야 한다. 그래서 이 파일은
// 파이썬 코드(herbivore_rl/env_v2/world.py `_step_predators_v3`·`_threat_motion`·`_threat_after`·`_player_new_mode`·
// `daynight_phase`·`_daynight_update`, env_v2/repertoire.py `cover_mult`·`control` 의 still)를 한 줄씩 옮긴다.
// 계약 문서와 코드가 다르면 코드를 따랐다(골든 생성기 herbivore_rl/export_golden_v3_threat.py 머리말에 차이를 적었다).
//
// 단위: 파이썬 단위다(길이 1 = 200 cm, 시간 1 = 결정 스텝 8/60 s, 속력 = 단위/스텝). Mass 층이 cm ÷ 200 으로 바꿔 넘긴다
// (계약 12-1). 기하는 모두 double 이다(파이썬 float64). 파이썬과 같은 순서로 계산해서 같은 입력이면 거의 비트 단위로 같다.
//
// 난수: 파이썬은 세 곳에 난수를 쓴다 — 배회 선회(보통 위협은 v1 스트림, 플레이어는 threats 스트림 3), 원거리형 포획 판정
// (v1 스트림 (M_base, N)개), 플레이어 새 모드(threats 스트림 2 에서 2개). 이 파일은 난수 스트림을 옮기지 않는다.
// 호출하는 쪽이 값을 입력으로 넣는다(FThreatStepInput 의 WanderTurn·RangedRoll·PlayerModeU0/U1). 골든은 파이썬이 실제로
// 뽑은 값을 넣는다. 언리얼은 FRandomStream 등으로 같은 분포의 값을 넣으면 된다(값까지 맞출 필요는 없다, 계약 7-7).
//
// 빠진 것: v3 R2 M7 노려보기(잠금·대치·물러남·플레이어 들킴)는 10-13 사람 결정으로 빠졌다. 이 파일에는 그 상태도 분기도 없다.
// M8 경보의 비명 점은 이 파일 밖이다(ResolveCatches 가 초식마다 잡은 위협 색인만 준다).
//
// ---------------------------------------------------------------------------------------------------------------
// 한 결정 스텝 (위협 하나. 순서가 계약이다 — 계약 7-1, world.py:2016-2145)
//   1  실거리 dist = |P_i - Q| (P_i = 초식 **이동 뒤**, Q = 위협 **이동 전**), inv = 1 / max(dist, 1e-9)
//      체감 거리 perceived = dist × det, 포획 거리 catch_d = dist × cov
//        cov = 은신처 안이면 행동별 은신 배수(웅크린 HIDE 4.0, GRAZE 1.5, SLEEP 2.5, 그 밖 1.0), 밖이면 1
//        det = max(cov, still ? c_still(1.8) : 1), still = FREEZE ∨ SLEEP ∨ 웅크린 HIDE(HIDE 도착)
//   2  cd ← max(cd - 1, 0). 잠 = 주행성 ∧ d ≥ sleep_dark(0.5). 사냥 = cd == 0 ∧ ¬잠
//   3  자는 잠행형은 ROAM·남은 0 으로. exh0 = 잠행형 ∧ EXHAUST, rest0 = 플레이어 ∧ REST. 사냥 ∧= ¬exh0 ∧ ¬rest0
//   4  시야 = 사냥 ∧ (플레이어 ∨ (perceived ≤ 14 ∧ (e·head)·inv ≥ cos 75°)). 플레이어는 맵 전체를 본다
//      표적 = 시야 중 perceived 최소, 동점이면 낮은 초식 색인. d_t = 그 체감 거리
//   5  배회 = head 를 turn 만큼 돌린 것. move = 표적 ? e_j·inv_j : 배회, 속력 = 기본 속력
//   6  유형별 상태 기계가 move·속력을 덮는다 (잠행형 7-4, 플레이어 7-5. 아래 Step 본문)
//   7  잠이면 move = head, 속력 × 0. 깨어 있는 주행성은 속력 × (1 - d) (박명 감속). 야행성·플레이어는 × 1
//   8  pos += move × 속력. 벽 밖으로 나간 축은 move 의 그 성분 부호를 뒤집고(반사) pos 를 [0, size] 로 자른다.
//      head ← normalize(move) (반사 뒤 move, 벽 자르기 전 방향), vel ← pos - 이동 전 pos (초식 관측 pred_approach)
//   9  포획: 사냥 ∧ catch_d ≤ 포획 반경 (원거리형은 ∧ roll < 0.02). 거리는 1 의 값(위협 이동 전)이다.
//      위협마다 한 스텝에 많아야 한 마리, catch_d 최소(동점 낮은 초식 색인). 잡으면 cd ← 플레이어 30 : 5
//  10  상태 갱신 (포획 판정 뒤 — world.py `_threat_after`)
//
// 쿨다운의 뜻 (코드 그대로, 계약 13-1 D10): 스텝 t 에 잡으면 cd = 5 다. 스텝 시작에 1 을 빼고 0 이면 사냥하므로
// t+1~t+4 는 사냥하지 않고(배회, 기본 속력), t+5 에 다시 잡을 수 있다. 플레이어는 30 → t+30 에 다시 잡는다.
// 잠든 동안에도 쿨다운은 줄어든다.
//
// 늑대 식사 중 제자리 (선택, FThreatConfig::bEatInPlace. 기본 끔 — 끄면 위 그대로이고 지금 골든과 비트 단위로 같다. 사람 결정 10-15 (B)):
//   켜면 보통 위협(플레이어 대역 아님)이 쿨다운 때문에 사냥하지 않는 스텝(1 을 뺀 뒤 cd > 0)에 움직이지 않는다. 7 의 잠과 같은 꼴로
//   move = head, 속력 0 이다(상태 기계 뒤, 밤잠·박명 배수 앞 — 6c). 그래서 위치 그대로·변위 0·heading = normalize(head) 다.
//   포획 판정·난수 소비는 그대로다. 식사 길이는 PredEatCd 가 정한다(통합 모드는 eco.IntegratedV3.WolfEatSeconds 로 38 = 5 초).
//   잡은 스텝 t 에는 이미 움직였고, t+1 ~ t+cd−1 동안 서 있다가 t+cd 에 다시 사냥한다. 파이썬 R3 세계의 같은 규칙:
//   features.threats.eat_in_place (world.py `_step_predators_v3` R3 (j)) —
//     eating = (pred_cd > 0) & ~pred_is_player;  move[eating] = pred_head[eating];  speed[eating] = 0
//
// 잠행-돌진형 (world.py:2299-2313, 2353-2368): 표적 체감 거리 ≤ 6 이면 돌진 시작(남은 12). 남은 > 0 이면 돌진(× 1.5,
// 표적 있으면 표적 쪽, 없으면 head), 남은 ≤ 0 이면 마지막 판정 스텝(× 0.2, head). 돌진 이동 12번 + 마지막 판정 1번이고,
// 마지막 판정에서 놓치면 탈진 30스텝(× 0.2 배회, 사냥 안 함), 돌진·마지막 판정 중 잡으면 곧바로 ROAM 이다.
// 표적이 없는 ROAM 은 잠행 속력이 아니라 **기본 속력**으로 배회한다(계약 13-1 D3).
//
// 플레이어 대역 (world.py:2314-2336, 2379-2394): 배회(× 0.4, 배회 선회) · 잠행(× 0.3, 가장 가까운 체감 거리 개체 쪽,
// 체감 ≤ 6 이면 돌진 시작) · 돌진(× 1.3 으로 20번 이동, 남은 ≤ 0 이면 멈춘 판정 스텝) · 휴식(멈춤, 사냥 안 함, 30스텝).
// 배회·잠행 모드도 닿으면 잡는다. 돌진 중 잡거나 돌진이 끝나면 휴식. 휴식·배회·잠행 길이가 끝나면 새 모드
// (u0 < 0.5 면 잠행, 아니면 배회. 길이 = 200 + ⌊u1·201⌋, 400 에서 자른다).
//
// 늑대 밤잠 점진화 (선택, FThreatConfig::bRealismNight. 기본 끔 — 끄면 위 1~10 그대로이고 지금 골든과 비트 단위로 같다):
//   파이썬 configs/v3_real1_night_on.yaml 의 realism_night 블록(world.py 모듈 docstring '(d) realism_night', `_rz_night_update`,
//   `_step_predators_v3` 의 hunt_dark·_zn_hunt)을 옮긴다. 켜면 잠이 어둠 d 의 순수 함수(IsAsleep)가 아니라 늑대마다 상태가 된다.
//   - 상태 (FThreatState): 잠(bAsleep), 활동도 NightAct ∈ [0, R](R = NightRampSteps), 눕는 중 bNightSettle, 깨어 있는 채 어둠인
//     업데이트 수 NightDarkK, 기상까지 남은 업데이트 NightWait(-1 = 기다리지 않음), 늑대별 지연 NightDelay, 지난 스텝 사냥 중 bNightHunt.
//   - NightInit (세계 생성·입양 때 한 번): 잠 = 주행성 ∧ d ≥ 0.5, 활동도 = 잠이면 0, 아니면 R.
//   - NightUpdate (스텝 끝 t + 1 의 어둠을 정한 뒤, 늑대 이동 뒤·리스폰 전 사슴 위치로): 아래 NightUpdate 머리 주석의 순서.
//   - Step 은 잠을 상태에서 읽고, 깜깜하면(d ≥ NightHuntDark) 지난 스텝에 사냥 중이 아니던 주행성 늑대는 사냥하지 않는다(새 사냥 없음 —
//     쫓던 사냥만 마저 끝낸다). 속력 배수 = 잠이면 0, 깨어 있는 주행성은 max(1 − d, NightFloor) × NightAct / R, 야행성 1.
//     스텝 끝에 bNightHunt = 표적 있음 ∨ 잠행형 돌진 상태(포획 뒤 갱신 다음 값)를 쓴다.
//
// 늑대 무리 협동 사냥 (선택, FThreatConfig::Pack. 기본 끔 — 끄면 위 그대로이고 지금 골든과 비트 단위로 같다. 야생 2단계 2, 사용자 10-17
//   '추천대로 끄고 2~4번 진행해', 파이썬 world.py wild_pack·`pack_goals`·`_pack_step`, configs/v3_wild2_pack_mirror.yaml):
//   위협끼리 서로 읽는 유일한 규칙이다. 그래서 Step 안이 아니라 부르는 쪽(EcoWorldV3 C2)이 모든 늑대가 움직이기 전에 정한다:
//     PackPeek   늑대마다 상태 사본으로 Step 을 한 번 돌려 이번 스텝의 사냥·표적·전력 걸음을 본다 (난수를 쓰지 않는다 — 선회·굴림은 결과와 무관)
//                앞장 = 보통 위협 ∧ 전력 걸음 ∧ 표적 있음, 돕는 늑대 = 보통 위협 ∧ 사냥 중 ∧ 전력 걸음 아님 (표적이 없거나 잠행 접근 중)
//     PackGoals  돕는 늑대마다 JoinR 안의 쫓기는 사슴 가운데 가장 가까운 것 → 도주 방향(사슴의 이번 이동, 서 있으면 앞장 → 사슴) →
//                향하는 은신처의 문(반지름 + 몸 여유) 또는 도주선 앞 Lead → 무대 안으로 자름 → WaitR 안이면 기다림(사슴 쪽을 본다)
//     Step 6b′   In.bPackHelp 면 move = PackDir, 속력 = 기다림 ? 0 : 기본 속력 (상태 기계 뒤, 6c 식사·6d 배부름·7 밤잠 배수 앞)
//   현실 근거: 늑대 무리 사냥 성공은 4 마리까지 는다(MacNulty 외 2012), 늑대는 길목에 떨어져 기다린다(Gable 외 2024)
// ---------------------------------------------------------------------------------------------------------------

#pragma once

#include <cmath>
#include <cstdint>

namespace EcoThreatV3
{
	// 위협 유형 (world.py PT_CHASER·PT_STALKER·PT_PLAYER). 원거리형은 유형이 아니라 추격형의 FThreatSpec::bRanged 다.
	enum class EThreatType : std::uint8_t
	{
		Chaser = 0,
		Stalker = 1,
		Player = 2,
	};

	// 잠행형 상태 (world.py ST_ROAM·ST_POUNCE·ST_EXHAUST). M7 의 대치(3)·물러남(4)은 빠졌다.
	enum class EStalkState : std::uint8_t
	{
		Roam = 0,
		Pounce = 1,
		Exhaust = 2,
	};

	// 플레이어 모드 (world.py PM_WANDER·PM_STALK·PM_CHARGE·PM_REST)
	enum class EPlayerMode : std::uint8_t
	{
		Wander = 0,
		Stalk = 1,
		Charge = 2,
		Rest = 3,
	};

	// 초식 행동 번호 (env_v2/repertoire.py 계약 순서 — EcoPolicyV3::kGraze.. 와 같은 값). 다른 v3 헤더에 기대지 않으려고 다시 적는다.
	inline constexpr std::uint8_t kPreyGraze = 0;
	inline constexpr std::uint8_t kPreyFlee = 1;
	inline constexpr std::uint8_t kPreyHide = 2;
	inline constexpr std::uint8_t kPreyFreeze = 3;
	inline constexpr std::uint8_t kPreySleep = 4;

	// normalize·inv 의 문턱 (env_v2/steering.py EPS)
	inline constexpr double kEps = 1e-9;

	// 야생 2단계 2 늑대 무리 협동 사냥 계수 (파이썬 features.wild_pack, configs/v3_wild2_pack_mirror.yaml 값). 단위는 파이썬 단위(1 = 2 m).
	// 기본 끔 = R1b 학습 세계 그대로. 켜는 쪽: EcoWorldV3 FWorldConfig::PackHunt (통합 모드 eco.IntegratedV3.PackHunt 기본 1)
	struct FPackHuntConfig
	{
		bool bEnabled = false;
		double JoinR = 60.0;     // join_r: 동료가 쫓는 사슴이 이 실거리 안이면 돕는다 (120 m = 무대 한 변. 처음 20 에서 하나만 골랐다 — 명세 RL_V3_WILD2_SPEC 5절)
		double Lead = 6.0;       // lead: 은신처가 없을 때 사슴 도주선 앞쪽 거리 (12 m = 잠행형 덮치기 거리와 같게, 어림)
		double DoorR = 15.0;     // door_r: 사슴이 향하는 은신처 = 가장자리까지 이 안 (30 m, 사슴의 도주 은신처 규칙 wild_flight.shelter_r 와 같다)
		double DoorCos = 0.5;    // door_cos: 도주 방향 ±acos(이 값) 안 (±60°, wild_flight.shelter_cos 와 같다)
		double WaitR = 1.0;      // wait_r: 목표 자리에 이만큼 가까우면 멈춰 사슴 쪽을 보고 기다린다 (2 m = 근접 포획 거리)
	};

	// 학습 세계 상수 (configs/default.yaml 위에 configs/v3_r1_on.yaml 을 덮은 값). 기본값이 계약이다 — 바꾸면 학습 밖이다.
	// 생성 헤더 ThreatGoldenVectorsV3.h 의 kCfg* 가 파이썬 설정에서 읽은 같은 값을 싣고, 시험이 하나씩 정확히 비교한다.
	struct FThreatConfig
	{
		// ---- 개체·포식자 (configs/default.yaml) ----
		double HerbSpeed = 0.6;                    // herb_speed (단위/스텝). 모든 위협 속력 계수는 이 값의 배수다
		double PredViewR = 14.0;                   // pred_view_r
		double PredFovCos = 0.25881904510252074;   // cos(radians(pred_fov_deg 150) * 0.5) — env/config.py pred_fov_cos 의 float64 값
		double PredMeleeCatchR = 1.0;              // pred_melee_catch_r
		double PredRangedCatchR = 3.0;             // pred_ranged_catch_r
		double PredRangedCatchP = 0.02;            // pred_ranged_catch_p (원거리형 스텝·초식당 포획 확률)
		double PredRangedSpeedMult = 0.6;          // pred_ranged_speed_mult
		double PredWanderTurn = 0.15;              // pred_wander_turn (배회 선회 U[-x, x] rad)
		std::int32_t PredEatCd = 5;                // pred_eat_cd (보통 위협 포획 뒤 쿨다운)

		// ---- 체감 거리 (features.repertoire, M1·M6) ----
		double CStill = 1.8;                       // c_still (정지 탐지: 표적 고르기 체감 거리에만)
		double CoverMultCrouch = 4.0;              // cover_mult_crouch (웅크린 HIDE, 은신처 안)
		double CoverMultGraze = 1.5;               // cover_mult_graze
		double CoverMultSleep = 2.5;               // cover_mult_sleep
		double CoverMultOther = 1.0;               // cover_mult_other (FLEE·FREEZE·가는 중 HIDE)

		// ---- 밤잠·박명 (features.pred_sleep) ----
		double SleepDark = 0.5;                    // sleep_dark (주행성 위협이 자는 어둠 d 문턱, d ≥ 이 값)
		bool bTwilightSlow = true;                 // twilight_slow (깨어 있는 주행성 위협 속력 × (1 - d))

		// ---- 잠행-돌진형 (features.threats, M3) ----
		double StalkDist = 6.0;                    // stalk_dist (돌진을 시작하는 표적 **체감** 거리)
		double StalkSpeed = 0.3;                   // stalk_speed (× HerbSpeed)
		double PounceSpeed = 1.5;                  // pounce_speed
		std::int32_t PounceSteps = 12;             // pounce_steps (돌진 이동 수)
		double ExhaustSpeed = 0.2;                 // exhaust_speed (탈진·마지막 판정 스텝)
		std::int32_t ExhaustSteps = 30;            // exhaust_steps

		// ---- 플레이어형 대역 (features.threats) ----
		double PlayerSpeeds[3] = {0.4, 0.3, 1.3};  // player_speeds [배회, 잠행, 돌진] (× HerbSpeed)
		std::int32_t PlayerModeStepsLo = 200;      // player_mode_steps [하, 상]
		std::int32_t PlayerModeStepsHi = 400;
		double PlayerStalkP = 0.5;                 // player_stalk_p (새 모드가 잠행일 확률)
		double PlayerChargeDist = 6.0;             // player_charge_dist (체감 거리)
		std::int32_t PlayerChargeSteps = 20;       // player_charge_steps
		std::int32_t PlayerRestSteps = 30;         // player_rest_steps
		double PlayerCatchR = 1.0;                 // player_catch_r
		std::int32_t PlayerCooldown = 30;          // player_cooldown

		// ---- 세계 무작위화 범위 (학습 세계, '언리얼 ⊆ 학습' 확인용. Step 은 읽지 않는다) ----
		double PredSpeedMultLo = 0.6;              // rand.pred_speed_mult (v3_r1_on overrides)
		double PredSpeedMultHi = 0.95;
		double RangedFracLo = 0.0;                 // rand.ranged_frac
		double RangedFracHi = 0.5;
		double StalkFracLo = 0.3;                  // threats.stalk_frac
		double StalkFracHi = 0.7;
		double NocturnalFracLo = 0.0;              // pred_sleep.nocturnal_frac
		double NocturnalFracHi = 0.25;
		double PlayerFrac = 0.5;                   // threats.player_frac
		std::int32_t PredatorCountLo = 2;          // rand.predator_count (양끝 포함)
		std::int32_t PredatorCountHi = 12;
		double WorldSizeLo = 60.0;                 // rand.world_size
		double WorldSizeHi = 110.0;
		std::int32_t DayPeriods[3] = {600, 900, 1800};   // daynight.periods (스텝)
		double Twilight = 0.05;                    // daynight.twilight (T 비율, 박명 폭 τ = 0.05·T 스텝)

		// ---- 늑대 밤잠 점진화 (features.realism_night, configs/v3_real1_night_on.yaml). 기본 끔 = R1b 학습 세계 그대로 ----
		// 켜는 쪽: 언리얼 통합 레벨 v3 모드 (사람 결정 H1 10-14: R1b 두뇌를 그대로 두고 언리얼에 먼저 넣는다 — R1b 측정으로 허용).
		// 아래 다섯 값은 켤 때 쓰는 값이고 골든 ThreatNightGoldenVectorsV3.h 의 kNightCfg* 가 파이썬 설정에서 읽은 같은 값을 싣는다.
		bool bRealismNight = false;                // 켜면 잠을 늑대별 상태(NightInit·NightUpdate)로 둔다. 끄면 IsAsleep(d) 그대로
		double NightSettleR = 8.0;                 // settle_r: 이 실거리 안에 사슴이 있으면 눕지 않는다 (16 m)
		double NightHuntDark = 1.0;                // hunt_dark: d ≥ 이 값이면 주행성 늑대는 새 사냥을 시작하지 않는다
		double NightFloor = 0.5;                   // night_floor: 해 진 뒤 깨어 있는 주행성 늑대 속력 배수 하한 (1 − SleepDark 이하)
		double NightSpread = 0.5;                  // spread: 늑대별 잠·기상 지연 최대 = ⌊spread × 박명 폭 τ⌋ 스텝
		std::int32_t NightRampSteps = 15;          // ramp_steps: 눕기·깨기에 걸리는 업데이트 수 (활동도 한 업데이트에 1 씩)

		// ---- 늑대 식사 중 제자리 (사람 결정 10-15 (B)). 기본 끔 = R1b 학습 세계 그대로 (쿨다운 동안 배회) ----
		// 켜는 쪽: 언리얼 통합 레벨 v3 모드 (eco.IntegratedV3.WolfEatSeconds 가 학습 5 스텝보다 길 때, PredEatCd 와 함께 바꾼다)
		bool bEatInPlace = false;                  // eat_in_place: 켜면 보통 위협이 쿨다운(식사) 동안 서 있는다 (Step 6c, 머리 주석 '늑대 식사 중 제자리')

		// ---- 야생 1단계 (w2) 늑대 포만 (사람 결정 10-15 (7), 파이썬 world.py '야생 1단계' (w2), configs/v3_wild1_mirror.yaml wild_satiation).
		//      기본 끔 = R1b 학습 세계 그대로. 켜는 쪽: EcoWorldV3 FWorldConfig::WildSatiation (하루 단위 sat_days 를 스텝으로 옮겨 넣는다) ----
		// 보통 위협이 잡으면 SatLeft ← SatSteps. Step 첫머리 쿨다운을 줄인 뒤 쿨다운 0 이고 SatLeft > 0 이면 이번 스텝은 배부름(bSated):
		// 사냥하지 않고(표적·포획 없음) SatLeft −1, 속력 × RestSpeed (6c 식사 제자리 뒤, 7 밤잠 배수 앞). 자지 않는 한 사슴에게 그대로 보인다
		bool bWildSatiation = false;
		std::int32_t SatSteps = 450;               // 반올림(sat_days 0.5 × 하루 900 스텝) = 60 초
		double RestSpeed = 0.3;                    // rest_speed: 배부른 늑대의 배회 속력 배수

		// ---- 은신처 안전·늑대 진입 금지 (사용자 보고 10-16 '은신처 안에서도 잡힌다', 파이썬 R3 realism_shelter (c)·(c′) — world.py 모듈 docstring,
		//      configs/v3_wild1_mirror.yaml realism_shelter: untargetable·player_too·block_predators 모두 true). 기본 끔 = R1b 학습 세계 그대로.
		//      켜는 쪽: EcoWorldV3 FWorldConfig::bShelterSafe (통합 모드 eco.IntegratedV3.ShelterSafe) ----
		// bShelterSafe: 은신처 원 안(FPreyView::bInCover — 이동 뒤 위치, 가장자리 포함) 사슴은 행동과 무관하게 표적이 되지 않고 잡히지 않는다
		//   (모든 위협 — player_too). bShelterBlock: 위협이 이동 뒤 원 안(|q − c| < r)이면 둘레 밖으로 밀어 둘레를 따라 미끄러지게 한다(Step 8, ShelterPush·
		//   ShelterTangent, 막다른 곳이면 돌아선다). 원 목록은 FThreatStepInput::Discs. 현실 근거: 빽빽한 덤불 속으로는 늑대가 따라 들어가 덮칠 수 없다
		bool bShelterSafe = false;
		bool bShelterBlock = false;

		// ---- 늑대 무리 협동 사냥 (야생 2단계 2, 머리 주석 '늑대 무리 협동 사냥'). 기본 끔. Step 은 읽지 않는다 — PackGoals 가 읽고 In 으로 넘긴다 ----
		FPackHuntConfig Pack;
	};

	// 은신처 진입 금지 상수 (world.py WALL_EPS·WALL_PASSES·WALL_DEAD_FRAC)
	inline constexpr double kShelterWallEps = 1.0e-6;      // 밀어낸 위치의 반지름 여유 (단위)
	inline constexpr std::int32_t kShelterPasses = 3;      // 밀어내기 바퀴 수
	inline constexpr double kShelterDeadFrac = 0.1;        // 가려던 거리의 이 몫도 못 가면 막다른 곳 → 돌아선다

	/** 위치 (X, Y) 가 은신처 원 안인가 (|q − c| < r, 둘레 위는 밖 — world.py `_rz_inside_disc`). Discs = (x, y, r) × Num. */
	inline bool InsideAnyDisc(double X, double Y, const double* Discs, std::int32_t Num)
	{
		for (std::int32_t k = 0; k < Num; ++k)
		{
			const double Ex = X - Discs[3 * k];
			const double Ey = Y - Discs[3 * k + 1];
			if (std::sqrt(Ex * Ex + Ey * Ey) < Discs[3 * k + 2])
			{
				return true;
			}
		}
		return false;
	}

	/**
	 * 밀어내기 (world.py `_rz_wall_push` 한 위협): 이동 뒤 위치 Q 가 원 k 안이면 c_k + (r_k + WallEps)·단위(Q − c_k) (Q 가 중심과 겹치면
	 * 단위(P − c_k), P = 이동 전 위치)로 옮긴다. 원 순서대로, 옮긴 원이 없을 때까지 최대 kShelterPasses 바퀴. 반환 = 한 번이라도 밀었나.
	 */
	inline bool ShelterPush(double& QX, double& QY, double PX, double PY, const double* Discs, std::int32_t Num)
	{
		if (Num <= 0 || !InsideAnyDisc(QX, QY, Discs, Num))
		{
			return false;
		}
		bool bPushed = false;
		for (std::int32_t Pass = 0; Pass < kShelterPasses; ++Pass)
		{
			bool bMoved = false;
			for (std::int32_t k = 0; k < Num; ++k)
			{
				const double Cx = Discs[3 * k];
				const double Cy = Discs[3 * k + 1];
				const double R = Discs[3 * k + 2];
				const double Ex = QX - Cx;
				const double Ey = QY - Cy;
				const double D = std::sqrt(Ex * Ex + Ey * Ey);
				if (!(D < R))
				{
					continue;
				}
				double Ux, Uy;
				if (D > kEps)
				{
					Ux = Ex / D;
					Uy = Ey / D;
				}
				else
				{
					const double Px = PX - Cx;
					const double Py = PY - Cy;
					const double Dp = std::sqrt(Px * Px + Py * Py);
					const double Dm = Dp > kEps ? Dp : kEps;
					Ux = Px / Dm;
					Uy = Py / Dm;
				}
				const double Rr = R + kShelterWallEps;
				QX = Cx + Rr * Ux;
				QY = Cy + Rr * Uy;
				bPushed = true;
				bMoved = true;
			}
			if (!bMoved)
			{
				break;
			}
		}
		return bPushed;
	}

	/**
	 * 접선 미끄러짐 (world.py `_rz_wall_tangent` 한 위협): 이전 위치 P 에서 둘레가 가장 가까운 원 k (|P − c_k| − r_k 최소, 같으면 낮은 번호)의
	 * 바깥 법선 n 에 대해 이동 V 의 안쪽 성분만 뺀 P + V − min(V·n, 0)·n 를 [0, Size] 로 자른다.
	 */
	inline void ShelterTangent(double PX, double PY, double VX, double VY, const double* Discs, std::int32_t Num, double Size,
							   double& OutX, double& OutY)
	{
		std::int32_t Kb = 0;
		double Best = 0.0, Bex = 0.0, Bey = 0.0, Bd = 0.0;
		for (std::int32_t k = 0; k < Num; ++k)
		{
			const double Ex = PX - Discs[3 * k];
			const double Ey = PY - Discs[3 * k + 1];
			const double D = std::sqrt(Ex * Ex + Ey * Ey);
			const double Edge = D - Discs[3 * k + 2];
			if (k == 0 || Edge < Best)
			{
				Kb = k;
				Best = Edge;
				Bex = Ex;
				Bey = Ey;
				Bd = D;
			}
		}
		(void)Kb;
		const double Nx = Bd > kEps ? Bex / Bd : 1.0;
		const double Ny = Bd > kEps ? Bey / Bd : 0.0;
		const double Dot = VX * Nx + VY * Ny;
		const double Vn = Dot < 0.0 ? Dot : 0.0;
		const double X = PX + (VX - Vn * Nx);
		const double Y = PY + (VY - Vn * Ny);
		OutX = X < 0.0 ? 0.0 : (X > Size ? Size : X);
		OutY = Y < 0.0 ? 0.0 : (Y > Size ? Size : Y);
	}

	// 위협 하나의 바뀌지 않는 성질 (세계 생성 때 정한다 — world.py:907-912, 976-1011)
	struct FThreatSpec
	{
		EThreatType Type = EThreatType::Chaser;
		bool bRanged = false;       // 원거리형 (추격형만. 잠행형·플레이어는 거짓)
		bool bNocturnal = false;    // 야행성 (밤에 자지 않고 박명 감속도 없다). 플레이어는 늘 참
		double BaseSpeed = 0.0;     // 기본 속력 (단위/스텝). 플레이어는 0 — 모드가 속력을 정한다
		double CatchRadius = 1.0;   // 포획 반경 (근접 1, 원거리 3, 플레이어 1)
	};

	// 위협 상태 (Mass FEcoThreatStateFragment 의 거울, 계약 12-2). 위의 칸이 다음 스텝의 입력이다.
	struct FThreatState
	{
		double PosX = 0.0;
		double PosY = 0.0;
		double HeadX = 1.0;         // 단위벡터 (normalize 가 영벡터를 내면 0 이 될 수 있다 — 파이썬과 같다)
		double HeadY = 0.0;
		double VelX = 0.0;          // 지난 스텝 실제 변위 (벽 자르기 포함). 초식 관측 pred_approach 가 읽는다
		double VelY = 0.0;
		std::int32_t Cooldown = 0;  // 포획 뒤 쿨다운 남은 스텝 (pred_cd)
		EStalkState StalkState = EStalkState::Roam;
		std::int32_t StalkLeft = 0;          // 돌진 남은 이동 수 / 탈진 남은 스텝 (stalk_left)
		EPlayerMode PlayerMode = EPlayerMode::Wander;
		std::int32_t PlayerLeft = 0;         // 모드 남은 스텝 (player_left)

		// 스텝 뒤 훅 (이번 스텝 결과. 다음 스텝 입력이 아니다)
		// bAsleep: 밤잠 점진화를 끄면 이번 스텝에 잤다(훅) — 초식 관측의 '자는 위협은 안 보인다'는 관측 때의 d 로 IsAsleep 을 다시 부른다.
		//          켜면(Cfg.bRealismNight) 늑대별 상태다 — NightInit·NightUpdate 가 쓰고 Step·관측이 읽는다.
		bool bAsleep = false;
		std::int32_t Target = -1;   // 이번 스텝 표적 (FPreyView 색인, 없으면 -1). 애니메이션 시선용

		// 밤잠 점진화 상태 (Cfg.bRealismNight 일 때만 쓴다. 끄면 기본값 그대로 두고 아무도 읽지 않는다 — world.py `_rz_night_reset`)
		std::int32_t NightAct = 0;       // 활동도 a ∈ [0, R] (속력 배수 a / R). NightInit 이 정한다
		bool bNightSettle = false;       // 눕는 중 (걸음을 늦추는 중)
		std::int32_t NightDarkK = 0;     // 깨어 있는 채 어둠(d ≥ 0.5)인 업데이트 수 (이어서)
		std::int32_t NightWait = -1;     // 기상까지 남은 업데이트 (-1 = 기다리지 않음)
		std::int32_t NightDelay = 0;     // 늑대별 잠·기상 지연 δ (NightDelayOf)
		bool bNightHunt = false;         // 지난 Step 에 사냥 중이었나 (표적 있음 ∨ 잠행형 돌진 상태). Step 이 쓰고 다음 Step·NightUpdate 가 읽는다

		// 야생 (w2) 늑대 포만 (Cfg.bWildSatiation 일 때만. 끄면 늘 0 — world.py pred_sat)
		std::int32_t SatLeft = 0;        // 남은 배부름 스텝 (먹기가 끝난 뒤부터 준다)
	};

	// 위협이 보는 초식 하나 (이번 스텝 이동 뒤 값)
	struct FPreyView
	{
		double X = 0.0;
		double Y = 0.0;
		std::uint8_t Behavior = kPreyGraze;  // 이번 스텝 행동 (Arbiter 뒤)
		bool bHideArrived = false;           // HIDE 도착(RepState arrived). 웅크림 = Behavior == HIDE ∧ 이것
		bool bInCover = false;               // 이동 뒤 위치가 은신처 원 안 (가장자리 포함, world.py `_in_cover`)
		bool bAlive = true;                  // 파이썬은 늘 참이다(리스폰). 거짓이면 표적·포획 후보에서 뺀다
		double MoveX = 0.0;                  // 이번 스텝 사슴 이동 (이동 뒤 − 이동 전). 늑대 무리 협동(PackGoals)의 도주 방향만 읽는다
		double MoveY = 0.0;
	};

	struct FThreatStepInput
	{
		const FPreyView* Prey = nullptr;
		std::int32_t NumPrey = 0;
		// 원거리형만 읽는다: 초식마다 U[0, 1) 하나 ([NumPrey]). roll < PredRangedCatchP 여야 잡는다. nullptr 면 원거리형은 잡지 않는다
		const double* RangedRoll = nullptr;
		double Dark = 0.0;          // 이번 스텝 어둠 d(t) (DayNightDark. 낮 고정 세계는 0)
		double WorldSize = 0.0;     // 정사각 맵 한 변 (벽 반사)
		double WanderTurn = 0.0;    // 배회 선회 (rad, U[-PredWanderTurn, PredWanderTurn]). 표적이 있어도 늘 넣는다
		double PlayerModeU0 = 0.0;  // 플레이어가 이번 스텝에 새 모드를 고를 때만 읽는다 (U[0, 1) 두 개)
		double PlayerModeU1 = 0.0;
		// 은신처 원 (x, y, r) × NumDiscs — Cfg.bShelterBlock 일 때만 읽는다 (통합 모드 = 레벨에서 받은 은신처 + 우리 은신처, FWorldConfig::Covers).
		// r 은 위협이 보는 반지름이다: EcoWorldV3 가 은신처 반지름 + 늑대 몸 여유(FWorldConfig::ShelterWolfMargin, 10-17)로 채운다
		const double* Discs = nullptr;
		std::int32_t NumDiscs = 0;
		// 늑대 무리 협동 (야생 2단계 2): 이 늑대가 이번 스텝 돕는 늑대면 참 (PackGoals 결과 — 부르는 쪽이 채운다). 기본 거짓 = 지금 그대로
		bool bPackHelp = false;
		bool bPackWait = false;     // 목표 자리에 닿아 기다림 (속력 0, PackDir = 사슴 쪽)
		double PackDirX = 0.0;      // 이동 방향 (단위)
		double PackDirY = 0.0;
	};

	struct FThreatStepResult
	{
		bool bAsleep = false;
		bool bHunting = false;
		bool bHasTarget = false;
		std::int32_t Target = -1;            // 표적 초식 색인
		double TargetPerceived = -1.0;       // 표적 체감 거리 d_t (없으면 -1)
		std::int32_t Caught = -1;            // 잡은 초식 색인 (없으면 -1)
		double Speed = 0.0;                  // 이번 스텝 적용 속력 (밤잠·박명 배수 뒤, 벽 반사 전)
		bool bWallHit = false;               // 벽 반사가 있었다
		bool bPounceStart = false;           // 잠행형 돌진 시작
		bool bChargeStart = false;           // 플레이어 돌진 시작
		bool bNewPlayerMode = false;         // 이번 스텝에 PlayerModeU0/U1 을 써서 새 모드를 골랐다
		bool bSated = false;                 // 야생 (w2): 이번 스텝 배불러 쉬었다 (world.py 훅 pred_sated)
		bool bRunning = false;               // 이번 이동이 전력 걸음 (world.py 훅 pred_running — 표적을 쫓는 추격형, 잠행형 돌진, 플레이어 돌진).
											 // 상태는 이동 때 값(포획 뒤 갱신 10a 전). 발소리 반경(EcoObservationV3::HearingRadius)이 읽는다
	};

	// ------------------------------------------------------------------------------------------------------------
	// 작은 도우미
	// ------------------------------------------------------------------------------------------------------------

	// steering.normalize: |v| > 1e-9 면 v/|v|, 아니면 0 (C++ GetSafeNormal 과 같은 뜻, 문턱 1e-9)
	inline void Normalize2(double& X, double& Y)
	{
		const double N = std::sqrt(X * X + Y * Y);
		if (N > kEps)
		{
			X = X / N;
			Y = Y / N;
		}
		else
		{
			X = 0.0;
			Y = 0.0;
		}
	}

	// 웅크림 (repertoire.control: crouch = HIDE ∧ arrived)
	inline bool PreyCrouched(const FPreyView& P)
	{
		return P.Behavior == kPreyHide && P.bHideArrived;
	}

	// 정지 탐지 대상 (repertoire.control: still = FREEZE ∨ SLEEP ∨ crouch). FLEE 놀람 정지·GRAZE 정지는 아니다
	inline bool PreyIsStill(const FPreyView& P)
	{
		return P.Behavior == kPreyFreeze || P.Behavior == kPreySleep || PreyCrouched(P);
	}

	// 은신처 안일 때의 행동별 은신 배수 (repertoire.cover_mult)
	inline double PreyCoverMult(const FPreyView& P, const FThreatConfig& Cfg)
	{
		if (PreyCrouched(P))
		{
			return Cfg.CoverMultCrouch;
		}
		if (P.Behavior == kPreyGraze)
		{
			return Cfg.CoverMultGraze;
		}
		if (P.Behavior == kPreySleep)
		{
			return Cfg.CoverMultSleep;
		}
		return Cfg.CoverMultOther;
	}

	// 포획 판정 거리 배수 cov (은신처 밖이면 1)
	inline double PreyCatchMult(const FPreyView& P, const FThreatConfig& Cfg)
	{
		return P.bInCover ? PreyCoverMult(P, Cfg) : 1.0;
	}

	// 표적 고르기 체감 거리 배수 det = max(cov, still ? c_still : 1) (world.py:2028-2029)
	inline double PreyDetectMult(const FPreyView& P, const FThreatConfig& Cfg)
	{
		const double Cov = PreyCatchMult(P, Cfg);
		const double Still = PreyIsStill(P) ? Cfg.CStill : 1.0;
		return Cov >= Still ? Cov : Still;
	}

	// 주행성 위협의 밤잠 (world.py `_daynight_update`: diurnal & d >= sleep_dark). 플레이어는 야행성으로 넣어 자지 않는다
	inline bool IsAsleep(const FThreatSpec& Spec, double Dark, const FThreatConfig& Cfg)
	{
		return !Spec.bNocturnal && Dark >= Cfg.SleepDark;
	}

	// 속력 배수 (world.py `_daynight_update` _pred_speed_mult): 잠 0, 깨어 있는 주행성 (1 - d), 야행성 1
	inline double SpeedMult(const FThreatSpec& Spec, double Dark, const FThreatConfig& Cfg)
	{
		if (IsAsleep(Spec, Dark, Cfg))
		{
			return 0.0;
		}
		if (!Spec.bNocturnal)
		{
			return Cfg.bTwilightSlow ? 1.0 - Dark : 1.0;
		}
		return 1.0;
	}

	// 세계 생성 때의 위협 성질 (world.py:907-912, 991-994, 1003-1010). PredSpeedMult 는 세계마다 하나(U[0.6, 0.95])다
	inline FThreatSpec MakeChaserSpec(double PredSpeedMult, bool bRanged, bool bNocturnal, const FThreatConfig& Cfg)
	{
		FThreatSpec S;
		S.Type = EThreatType::Chaser;
		S.bRanged = bRanged;
		S.bNocturnal = bNocturnal;
		const double Base = Cfg.HerbSpeed * PredSpeedMult;
		S.BaseSpeed = bRanged ? Base * Cfg.PredRangedSpeedMult : Base;
		S.CatchRadius = bRanged ? Cfg.PredRangedCatchR : Cfg.PredMeleeCatchR;
		return S;
	}

	// 잠행형은 근접형이다 (v1 원거리형 배치를 덮는다, world.py:989-994)
	inline FThreatSpec MakeStalkerSpec(double PredSpeedMult, bool bNocturnal, const FThreatConfig& Cfg)
	{
		FThreatSpec S = MakeChaserSpec(PredSpeedMult, false, bNocturnal, Cfg);
		S.Type = EThreatType::Stalker;
		return S;
	}

	// 플레이어 대역: 기본 속력 0(모드가 정한다), 포획 player_catch_r, 밤에 자지 않는다
	inline FThreatSpec MakePlayerSpec(const FThreatConfig& Cfg)
	{
		FThreatSpec S;
		S.Type = EThreatType::Player;
		S.bRanged = false;
		S.bNocturnal = true;
		S.BaseSpeed = 0.0;
		S.CatchRadius = Cfg.PlayerCatchR;
		return S;
	}

	// 플레이어 새 모드 (world.py `_player_new_mode`, threats 스트림 2 에서 U0·U1). 세계 생성 때도 한 번 부른다
	inline void PickPlayerMode(FThreatState& T, double U0, double U1, const FThreatConfig& Cfg)
	{
		const std::int32_t Lo = Cfg.PlayerModeStepsLo;
		const std::int32_t Hi = Cfg.PlayerModeStepsHi;
		T.PlayerMode = U0 < Cfg.PlayerStalkP ? EPlayerMode::Stalk : EPlayerMode::Wander;
		const std::int32_t Len = Lo + static_cast<std::int32_t>(U1 * static_cast<double>(Hi - Lo + 1));   // int() 는 0 쪽 버림
		T.PlayerLeft = Len < Hi ? Len : Hi;
	}

	// 어둠 d(t) (world.py `daynight_phase`, 계약 7-6). OutRemain 이 있으면 다음 전환까지 남은 스텝 r ∈ [1, Period/2] 을 쓴다.
	//   h = T/2, s = (t + o) mod T, e = s mod h, r = h - e, k = min(e, r), x = k / (2τ)
	//   낮(s < h): d = max(0.5 - x, 0), 밤: d = min(0.5 + x, 1). 전환 스텝은 정확히 0.5 다(밤잠 문턱과 정확히 같다 — 빼지 않는다)
	inline double DayNightDark(std::int64_t Step, std::int32_t Period, std::int32_t Offset, std::int32_t TwSteps,
							   std::int32_t* OutRemain = nullptr)
	{
		const std::int64_t H = Period / 2;
		std::int64_t S = (Step + Offset) % Period;
		if (S < 0)
		{
			S += Period;   // 파이썬 % 는 늘 0 이상
		}
		const std::int64_t E = S % H;
		const std::int64_t R = H - E;
		const std::int64_t K = E < R ? E : R;
		const double X = static_cast<double>(K) / (2.0 * static_cast<double>(TwSteps));
		if (OutRemain != nullptr)
		{
			*OutRemain = static_cast<std::int32_t>(R);
		}
		if (S >= H)
		{
			const double D = 0.5 + X;
			return D < 1.0 ? D : 1.0;
		}
		const double D = 0.5 - X;
		return D > 0.0 ? D : 0.0;
	}

	// ------------------------------------------------------------------------------------------------------------
	// 늑대 밤잠 점진화 (Cfg.bRealismNight, world.py realism_night)
	// ------------------------------------------------------------------------------------------------------------

	// 늑대별 지연 해시의 첫 입력 (world.py NIGHT_TAG). 사건 결정 지연 505·세계 난수 태그와 겹치지 않는다
	inline constexpr std::uint64_t kNightTag = 606;

	// SplitMix64 마무리 (env_v2/repertoire.py `_mix64`, EcoRepertoire.h Mix64 와 같은 식. 이 파일은 다른 v3 헤더에 기대지 않는다)
	inline std::uint64_t NightMix64(std::uint64_t Z)
	{
		Z = (Z ^ (Z >> 30)) * 0xBF58476D1CE4E5B9ULL;
		Z = (Z ^ (Z >> 27)) * 0x94D049BB133111EBULL;
		return Z ^ (Z >> 31);
	}

	// 늑대별 잠·기상 지연 δ = H(606, Seed, Slot) mod (MaxDelay + 1) ∈ [0, MaxDelay] (world.py `night_delays`).
	// H = repertoire.mix_chain (h = 0, 입력마다 h = Mix64((h ^ x) + 0x9E3779B97F4A7C15)). Seed·Slot 의 음수는 2 의 보수 그대로 (numpy astype uint64)
	inline std::int32_t NightDelayOf(std::int64_t Seed, std::int64_t Slot, std::int32_t MaxDelay)
	{
		if (MaxDelay <= 0)
		{
			return 0;
		}
		std::uint64_t H = 0;
		H = NightMix64((H ^ kNightTag) + 0x9E3779B97F4A7C15ULL);
		H = NightMix64((H ^ static_cast<std::uint64_t>(Seed)) + 0x9E3779B97F4A7C15ULL);
		H = NightMix64((H ^ static_cast<std::uint64_t>(Slot)) + 0x9E3779B97F4A7C15ULL);
		return static_cast<std::int32_t>(H % static_cast<std::uint64_t>(static_cast<std::int64_t>(MaxDelay) + 1));
	}

	// 지연 최대 = ⌊spread × τ⌋ (τ = 박명 폭 스텝. 낮 고정 세계는 τ 를 0 으로 넣는다 — 어둠이 없다)
	inline std::int32_t NightMaxDelay(std::int32_t TwSteps, const FThreatConfig& Cfg)
	{
		return TwSteps > 0 ? static_cast<std::int32_t>(std::floor(Cfg.NightSpread * static_cast<double>(TwSteps))) : 0;
	}

	// 처음 상태 (world.py `_rz_night_update` 의 fresh): 이미 어두우면(d ≥ 0.5) 주행성은 자고 있다. 야행성·플레이어는 늘 깨어 있다
	inline void NightInit(const FThreatSpec& Spec, FThreatState& T, double Dark, std::int32_t Delay, const FThreatConfig& Cfg)
	{
		T.NightDelay = Delay;
		T.bAsleep = !Spec.bNocturnal && Dark >= Cfg.SleepDark;
		T.NightAct = T.bAsleep ? 0 : Cfg.NightRampSteps;
		T.bNightSettle = false;
		T.NightDarkK = 0;
		T.NightWait = -1;
		T.bNightHunt = false;   // world.py `_rz_night_reset`: 처음에는 사냥 중이 아니다
	}

	// 지금 잠 (Step·관측이 읽는다): 켜면 늑대별 상태, 끄면 어둠의 순수 함수
	inline bool IsAsleepNow(const FThreatSpec& Spec, const FThreatState& T, double Dark, const FThreatConfig& Cfg)
	{
		return Cfg.bRealismNight ? T.bAsleep : IsAsleep(Spec, Dark, Cfg);
	}

	// 밤잠 점진화의 속력 배수 (world.py `_rz_night_update` 끝): 잠 0, 깨어 있는 주행성 max(1 − d, NightFloor) × a / R, 야행성 1.
	// d 는 그 업데이트의 어둠 = 다음 Step 의 In.Dark (둘 사이에 어둠이 바뀌지 않는다). 파이썬과 같은 순서의 double 계산이다
	inline double NightSpeedMult(const FThreatSpec& Spec, const FThreatState& T, double Dark, const FThreatConfig& Cfg)
	{
		if (T.bAsleep)
		{
			return 0.0;
		}
		if (Spec.bNocturnal)
		{
			return 1.0;
		}
		const double Slow = Cfg.bTwilightSlow ? 1.0 - Dark : 1.0;
		const double Base = Slow >= Cfg.NightFloor ? Slow : Cfg.NightFloor;   // 파이썬 max(slow, night_floor)
		const double Level = Cfg.NightRampSteps > 0
								 ? static_cast<double>(T.NightAct) / static_cast<double>(Cfg.NightRampSteps)
								 : 1.0;
		return Base * Level;
	}

	// NightUpdate 한 번의 결과 (기록·화면·골든 대조. 상태는 T 에 있다)
	struct FNightUpdateResult
	{
		bool bWake = false;          // 이번 업데이트에 깼다 (활동도 0 에서 오르기 시작)
		bool bSettleStart = false;   // 눕기 시작
		bool bSettleAbort = false;   // 눕다가 다시 일어났다 (사냥·사슴·새벽)
		bool bOnset = false;         // 잠들었다
		bool bBlockDeer = false;     // 누울 차례인데 settle_r 안에 사슴이 있어 못 누웠다
		bool bBlockHunt = false;     // 누울 차례인데 사냥 중이라 못 누웠다
		bool bNearChecked = false;   // 사슴 거리를 쟀다 (눕는 중이거나 누울 차례)
		bool bNear = false;          // 잰 결과 settle_r 안에 사슴이 있다
	};

	// 한 업데이트 (world.py `_rz_night_update`, 주행성 늑대 하나). 스텝 끝 t + 1 의 어둠 Dark 와, 늑대 이동 뒤·리스폰 전 사슴 위치로 부른다
	// (이번 스텝에 죽은 사슴도 그 자리에서 센다 — 파이썬 모든 슬롯). R = NightRampSteps, bDark = Dark ≥ SleepDark, bHunt = T.bNightHunt:
	//   자고 있음:  bDark 면 Wait = -1. 아니면 Wait < 0 이면 Wait = Delay; Wait == 0 이면 깸(Wait = -1, Act = 0), 아니면 --Wait.
	//               (깬 늑대는 같은 업데이트에 아래 '깨어 있음'을 탄다 → Act = 1)
	//   깨어 있음:  DarkK = bDark ? DarkK + 1 : 0.
	//               bNear = 실거리 ≤ SettleR 인 사슴이 있다 (bDark ∧ (bSettle ∨ DarkK > Delay) 일 때만 잰다)
	//               bCalm = bDark ∧ ¬bHunt ∧ ¬bNear, bReady = ¬bSettle ∧ bDark ∧ DarkK > Delay
	//               bSettle ∧ ¬bCalm → 다시 일어남, bReady ∧ bCalm → 눕기 시작
	//               bSettle 이면 --Act, Act ≤ 0 이면 잠듦(Act 0, bSettle 거짓, DarkK 0). 아니면 Act = min(Act + 1, R)
	//   자는 늑대·야행성의 DarkK 는 0 이다(파이썬 np.where(awake & dark, DarkK + 1, 0)).
	inline FNightUpdateResult NightUpdate(const FThreatSpec& Spec, FThreatState& T, double Dark, const FPreyView* Prey,
										  std::int32_t NumPrey, const FThreatConfig& Cfg)
	{
		FNightUpdateResult R;
		if (Spec.bNocturnal)
		{
			T.bAsleep = false;
			T.NightDarkK = 0;
			return R;
		}
		const std::int32_t Ramp = Cfg.NightRampSteps;
		const bool bDark = Dark >= Cfg.SleepDark;
		if (T.bAsleep)
		{
			if (bDark)
			{
				T.NightWait = -1;
			}
			else
			{
				if (T.NightWait < 0)
				{
					T.NightWait = T.NightDelay;
				}
				if (T.NightWait == 0)
				{
					T.bAsleep = false;
					T.NightWait = -1;
					T.NightAct = 0;
					R.bWake = true;
				}
				else
				{
					--T.NightWait;
				}
			}
		}
		if (T.bAsleep)
		{
			T.NightDarkK = 0;
			return R;
		}
		T.NightDarkK = bDark ? T.NightDarkK + 1 : 0;
		bool bNear = false;
		if (bDark && (T.bNightSettle || T.NightDarkK > T.NightDelay))
		{
			R.bNearChecked = true;
			for (std::int32_t i = 0; i < NumPrey && !bNear; ++i)
			{
				if (!Prey[i].bAlive)
				{
					continue;
				}
				const double DX = Prey[i].X - T.PosX;
				const double DY = Prey[i].Y - T.PosY;
				bNear = std::sqrt(DX * DX + DY * DY) <= Cfg.NightSettleR;
			}
			R.bNear = bNear;
		}
		const bool bHunt = T.bNightHunt;
		const bool bCalm = bDark && !bHunt && !bNear;
		const bool bReady = !T.bNightSettle && bDark && T.NightDarkK > T.NightDelay;
		if (T.bNightSettle && !bCalm)
		{
			T.bNightSettle = false;
			R.bSettleAbort = true;
		}
		else if (bReady && bCalm)
		{
			T.bNightSettle = true;
			R.bSettleStart = true;
		}
		R.bBlockDeer = bReady && !bHunt && bNear;
		R.bBlockHunt = bReady && bHunt;
		if (T.bNightSettle)
		{
			--T.NightAct;
			if (T.NightAct <= 0)
			{
				T.NightAct = 0;
				T.bAsleep = true;
				T.bNightSettle = false;
				T.NightDarkK = 0;
				R.bOnset = true;
			}
		}
		else
		{
			T.NightAct = T.NightAct + 1 < Ramp ? T.NightAct + 1 : Ramp;
		}
		return R;
	}

	// ------------------------------------------------------------------------------------------------------------
	// 한 결정 스텝 (위협 하나)
	// ------------------------------------------------------------------------------------------------------------

	// 위협 하나의 결정 스텝. T 를 갱신하고 이번 스텝 결과를 낸다. 위협끼리는 서로 읽지 않으므로(world.py 의 위협 축 계산은 모두
	// 행마다 독립이다) 위협 슬롯 순서로 하나씩 부르면 파이썬의 한 스텝과 같다. 초식 위치는 모든 위협에 같은 '이동 뒤' 값을 준다.
	inline FThreatStepResult Step(const FThreatSpec& Spec, FThreatState& T, const FThreatStepInput& In,
								  const FThreatConfig& Cfg)
	{
		FThreatStepResult R;
		const bool bStalker = Spec.Type == EThreatType::Stalker;
		const bool bPlayer = Spec.Type == EThreatType::Player;
		const double QX = T.PosX;    // 이동 전 위치·heading
		const double QY = T.PosY;
		const double HX = T.HeadX;
		const double HY = T.HeadY;

		// 2. 쿨다운·잠·사냥 (world.py:2034-2037). 밤잠 점진화를 켜면 잠은 늑대별 상태이고(지난 NightUpdate), 깜깜하면(d ≥ hunt_dark)
		//    지난 스텝에 사냥 중이 아니던 주행성 늑대는 새 사냥을 시작하지 않는다 (world.py `_step_predators_v3` 의 hunt_dark 줄)
		T.Cooldown = T.Cooldown - 1 > 0 ? T.Cooldown - 1 : 0;
		const bool bAsleep = IsAsleepNow(Spec, T, In.Dark, Cfg);
		// 야생 (w2) 포만: 먹기(쿨다운)가 끝났고 배부름이 남았으면 이번 스텝은 쉰다 (잠과 무관하게 남은 스텝이 준다 — world.py 그대로)
		const bool bSated = Cfg.bWildSatiation && T.Cooldown == 0 && T.SatLeft > 0;
		if (bSated)
		{
			--T.SatLeft;
		}
		bool bHunting = T.Cooldown == 0 && !bAsleep && !bSated;
		if (Cfg.bRealismNight && In.Dark >= Cfg.NightHuntDark)
		{
			bHunting = bHunting && (Spec.bNocturnal || T.bNightHunt);
		}

		// 3. 자는 잠행형은 처음 상태로, 탈진·휴식은 사냥하지 않는다 (world.py:2040-2054)
		if (bStalker && bAsleep)
		{
			T.StalkState = EStalkState::Roam;
			T.StalkLeft = 0;
		}
		const bool bExh0 = bStalker && T.StalkState == EStalkState::Exhaust;
		const bool bRest0 = bPlayer && T.PlayerMode == EPlayerMode::Rest;
		bHunting = bHunting && !bExh0 && !bRest0;

		// 1·4. 체감 거리와 표적 (world.py:2022-2033, 2055-2063). 동점이면 낮은 색인 — 엄격한 < 로 앞에서부터 훑는다
		std::int32_t J = -1;
		double DT = 0.0;
		if (bHunting)
		{
			for (std::int32_t i = 0; i < In.NumPrey; ++i)
			{
				const FPreyView& P = In.Prey[i];
				if (!P.bAlive || (Cfg.bShelterSafe && P.bInCover))   // 은신처 안 사슴은 표적이 아니다 (realism_shelter untargetable)
				{
					continue;
				}
				const double DX = P.X - QX;
				const double DY = P.Y - QY;
				const double Dist = std::sqrt(DX * DX + DY * DY);
				const double Perceived = Dist * PreyDetectMult(P, Cfg);
				bool bVis = bPlayer;
				if (!bVis)
				{
					const double Inv = 1.0 / (Dist > kEps ? Dist : kEps);
					bVis = Perceived <= Cfg.PredViewR && (DX * HX + DY * HY) * Inv >= Cfg.PredFovCos;
				}
				if (bVis && (J < 0 || Perceived < DT))
				{
					J = i;
					DT = Perceived;
				}
			}
		}
		const bool bHasTarget = J >= 0;

		// 5. 배회 선회와 기본 이동 (world.py:2066-2075)
		const double C = std::cos(In.WanderTurn);
		const double S = std::sin(In.WanderTurn);
		const double WX = HX * C - HY * S;
		const double WY = HX * S + HY * C;
		double MX = WX;
		double MY = WY;
		if (bHasTarget)
		{
			const double DX = In.Prey[J].X - QX;
			const double DY = In.Prey[J].Y - QY;
			const double Dist = std::sqrt(DX * DX + DY * DY);
			const double Inv = 1.0 / (Dist > kEps ? Dist : kEps);
			MX = DX * Inv;
			MY = DY * Inv;
		}
		double Speed = Spec.BaseSpeed;

		// 6a. 잠행-돌진형 (world.py `_threat_motion`:2299-2313)
		bool bFinal = false;
		bool bDash = false;
		if (bStalker)
		{
			const bool bRoam = T.StalkState == EStalkState::Roam;
			const bool bStart = bRoam && bHasTarget && DT <= Cfg.StalkDist;
			if (bStart)
			{
				T.StalkState = EStalkState::Pounce;
				T.StalkLeft = Cfg.PounceSteps;
				R.bPounceStart = true;
			}
			const bool bStalking = bRoam && bHasTarget && !bStart;
			const bool bPounce = T.StalkState == EStalkState::Pounce;
			bFinal = bPounce && T.StalkLeft <= 0;
			bDash = bPounce && !bFinal;
			if (bStalking)
			{
				Speed = Cfg.StalkSpeed * Cfg.HerbSpeed;
			}
			if (bDash)
			{
				Speed = Cfg.PounceSpeed * Cfg.HerbSpeed;
			}
			if (bExh0 || bFinal)
			{
				Speed = Cfg.ExhaustSpeed * Cfg.HerbSpeed;
			}
			if ((bDash && !bHasTarget) || bFinal)
			{
				MX = HX;
				MY = HY;
			}
		}

		// 6b. 플레이어 대역 (world.py `_threat_motion`:2314-2336)
		if (bPlayer)
		{
			if (T.PlayerMode == EPlayerMode::Stalk && bHasTarget && DT <= Cfg.PlayerChargeDist)
			{
				T.PlayerMode = EPlayerMode::Charge;
				T.PlayerLeft = Cfg.PlayerChargeSteps;
				R.bChargeStart = true;
			}
			if (T.PlayerMode == EPlayerMode::Wander)
			{
				Speed = Cfg.PlayerSpeeds[0] * Cfg.HerbSpeed;
				MX = WX;
				MY = WY;
			}
			else if (T.PlayerMode == EPlayerMode::Stalk)
			{
				Speed = Cfg.PlayerSpeeds[1] * Cfg.HerbSpeed;   // 표적 쪽 (표적이 없으면 배회)
			}
			else if (T.PlayerMode == EPlayerMode::Charge && T.PlayerLeft > 0)
			{
				Speed = Cfg.PlayerSpeeds[2] * Cfg.HerbSpeed;
				if (!bHasTarget)
				{
					MX = HX;
					MY = HY;
				}
			}
			else   // 휴식, 또는 돌진 뒤 마지막 판정 스텝
			{
				Speed = 0.0;
				MX = HX;
				MY = HY;
			}
		}

		// 6b′. 늑대 무리 협동 (켰을 때만, world.py `_pack_step`): 돕는 늑대(보통 위협·사냥 중·전력 걸음 아님 — PackPeek·PackGoals 가 정해 In 으로 넘긴다)는
		//      배회·잠행 접근 대신 PackDir 쪽으로 기본 속력, 기다림이면 속력 0. 상태 기계 뒤, 6c 식사·6d 배부름·7 밤잠 배수 앞 (파이썬과 같은 자리)
		if (In.bPackHelp && !bPlayer && bHunting
			&& !((Spec.Type == EThreatType::Chaser && bHasTarget) || (bStalker && T.StalkState == EStalkState::Pounce)))
		{
			MX = In.PackDirX;
			MY = In.PackDirY;
			Speed = In.bPackWait ? 0.0 : Spec.BaseSpeed;
		}

		// 6c. 식사 중 제자리 (켰을 때만, world.py R3 (j) eat_in_place): 쿨다운 때문에 사냥하지 않는 보통 위협은 잠처럼 move = head,
		//     속력 0 (상태 기계 뒤, 밤잠 배수 앞 — 파이썬과 같은 자리. 뒤의 배수를 곱해도 0 이다)
		if (Cfg.bEatInPlace && !bPlayer && T.Cooldown > 0)
		{
			MX = HX;
			MY = HY;
			Speed = 0.0;
		}
		// 6d. 야생 (w2): 배부른 늑대는 느리게 어슬렁거린다 (표적이 없으므로 move 는 배회. 밤잠 배수 앞 — world.py 그대로)
		if (bSated)
		{
			Speed = Speed * Cfg.RestSpeed;
		}

		// 7. 밤잠·박명 (world.py:2078-2080). 밤잠 점진화를 켜면 배수는 늑대별 활동도를 따른다 (NightSpeedMult)
		if (bAsleep)
		{
			MX = HX;
			MY = HY;
		}
		Speed = Speed * (Cfg.bRealismNight ? NightSpeedMult(Spec, T, In.Dark, Cfg) : SpeedMult(Spec, In.Dark, Cfg));

		// 8. 이동·벽 반사·heading·변위 (world.py:2083-2113)
		double NX = QX + MX * Speed;
		double NY = QY + MY * Speed;
		// 8a. 은신처 진입 금지 (켰을 때만, world.py R3 (c′)): 원 안이면 둘레 밖으로 (벽 반사 전)
		const bool bBlock = Cfg.bShelterBlock && In.Discs != nullptr && In.NumDiscs > 0;
		const double SVX = MX * Speed;   // 이번 스텝 이동 (벽 반사 전 방향 — 접선 미끄러짐·막다른 곳에 쓴다)
		const double SVY = MY * Speed;
		const bool bPushed = bBlock && ShelterPush(NX, NY, QX, QY, In.Discs, In.NumDiscs);
		if (NX < 0.0 || NX > In.WorldSize)
		{
			MX = -MX;
			R.bWallHit = true;
		}
		if (NY < 0.0 || NY > In.WorldSize)
		{
			MY = -MY;
			R.bWallHit = true;
		}
		NX = NX < 0.0 ? 0.0 : (NX > In.WorldSize ? In.WorldSize : NX);
		NY = NY < 0.0 ? 0.0 : (NY > In.WorldSize ? In.WorldSize : NY);
		if (bBlock)
		{
			// 밀어내도(또는 clip 뒤에) 원 안이면 이전 위치에서 접선으로만, 그래도 원 안이면 이전 위치. 막다른 곳이면 돌아선다 (world.py 그대로.
			// 플레이어의 막다른 곳 포기·reset 때 원 안 위협 옮기기는 옮기지 않았다 — 통합 무대는 플레이어가 없고 늑대는 모서리에서 시작한다)
			const bool bInside = InsideAnyDisc(NX, NY, In.Discs, In.NumDiscs);
			if (bInside)
			{
				double AX = 0.0, AY = 0.0;
				ShelterTangent(QX, QY, SVX, SVY, In.Discs, In.NumDiscs, In.WorldSize, AX, AY);
				const bool bOk = !InsideAnyDisc(AX, AY, In.Discs, In.NumDiscs);
				NX = bOk ? AX : QX;
				NY = bOk ? AY : QY;
			}
			const double Want = std::sqrt(SVX * SVX + SVY * SVY);
			const double DvX = NX - QX;
			const double DvY = NY - QY;
			if ((bPushed || bInside) && Want > kEps && std::sqrt(DvX * DvX + DvY * DvY) < kShelterDeadFrac * Want)
			{
				MX = -SVX / Want;
				MY = -SVY / Want;
			}
		}
		Normalize2(MX, MY);
		T.HeadX = MX;
		T.HeadY = MY;
		T.VelX = NX - QX;
		T.VelY = NY - QY;
		T.PosX = NX;
		T.PosY = NY;

		// 8b. 전력 걸음 훅 (realism_hearing 의 pred_running, 포획 뒤 상태 갱신 전 값)
		R.bRunning = (Spec.Type == EThreatType::Chaser && bHasTarget) || (bStalker && T.StalkState == EStalkState::Pounce)
					 || (bPlayer && T.PlayerMode == EPlayerMode::Charge);

		// 9. 포획 (world.py:2115-2125, 2138-2141). 거리는 위협 이동 전 위치로 잰 1 의 값이다
		std::int32_t K = -1;
		double KD = 0.0;
		if (bHunting)
		{
			for (std::int32_t i = 0; i < In.NumPrey; ++i)
			{
				const FPreyView& P = In.Prey[i];
				if (!P.bAlive || (Cfg.bShelterSafe && P.bInCover))   // 은신처 안 사슴은 잡히지 않는다 (realism_shelter (c))
				{
					continue;
				}
				const double DX = P.X - QX;
				const double DY = P.Y - QY;
				const double CatchD = std::sqrt(DX * DX + DY * DY) * PreyCatchMult(P, Cfg);
				if (!(CatchD <= Spec.CatchRadius))
				{
					continue;
				}
				if (Spec.bRanged && !(In.RangedRoll != nullptr && In.RangedRoll[i] < Cfg.PredRangedCatchP))
				{
					continue;
				}
				if (K < 0 || CatchD < KD)
				{
					K = i;
					KD = CatchD;
				}
			}
		}
		const bool bGot = K >= 0;
		if (bGot)
		{
			T.Cooldown = bPlayer ? Cfg.PlayerCooldown : Cfg.PredEatCd;
			if (Cfg.bWildSatiation && !bPlayer)
			{
				T.SatLeft = Cfg.SatSteps;   // 야생 (w2): 먹기가 끝난 뒤 배부름 (플레이어형 위협은 늘 0)
			}
		}

		// 10a. 잠행형 상태 갱신 (world.py `_threat_after`:2353-2368)
		if (bStalker)
		{
			if (T.StalkState == EStalkState::Pounce && bGot)
			{
				T.StalkState = EStalkState::Roam;
				T.StalkLeft = 0;
			}
			if (bFinal && !bGot)
			{
				T.StalkState = Cfg.ExhaustSteps > 0 ? EStalkState::Exhaust : EStalkState::Roam;
				T.StalkLeft = Cfg.ExhaustSteps;
			}
			if (bDash && !bGot)
			{
				T.StalkLeft -= 1;
			}
			if (bExh0)
			{
				T.StalkLeft -= 1;
				if (T.StalkLeft <= 0)
				{
					T.StalkState = EStalkState::Roam;
					T.StalkLeft = 0;
				}
			}
		}

		// 10b. 플레이어 모드 갱신 (world.py `_threat_after`:2379-2394)
		if (bPlayer)
		{
			if (T.PlayerMode == EPlayerMode::Charge)
			{
				if (bGot || T.PlayerLeft <= 0)
				{
					T.PlayerMode = EPlayerMode::Rest;
					T.PlayerLeft = Cfg.PlayerRestSteps;
					if (Cfg.PlayerRestSteps <= 0)
					{
						PickPlayerMode(T, In.PlayerModeU0, In.PlayerModeU1, Cfg);
						R.bNewPlayerMode = true;
					}
				}
				else
				{
					T.PlayerLeft -= 1;
				}
			}
			else   // 배회·잠행·휴식: 남은 길이를 줄이고 끝나면 새 모드
			{
				T.PlayerLeft -= 1;
				if (T.PlayerLeft <= 0)
				{
					PickPlayerMode(T, In.PlayerModeU0, In.PlayerModeU1, Cfg);
					R.bNewPlayerMode = true;
				}
			}
		}

		// 10c. 밤잠 점진화: 이번 스텝에 사냥 중이었나 (표적 있음, 또는 상태 갱신 뒤 잠행형 돌진) — 다음 NightUpdate·Step 이 읽는다
		if (Cfg.bRealismNight)
		{
			T.bNightHunt = bHasTarget || (bStalker && T.StalkState == EStalkState::Pounce);
		}

		T.bAsleep = bAsleep;
		T.Target = J;
		R.bAsleep = bAsleep;
		R.bHunting = bHunting;
		R.bSated = bSated;
		R.bHasTarget = bHasTarget;
		R.Target = J;
		R.TargetPerceived = bHasTarget ? DT : -1.0;
		R.Caught = K;
		R.Speed = Speed;
		return R;
	}

	// ------------------------------------------------------------------------------------------------------------
	// 늑대 무리 협동 사냥 (야생 2단계 2 — 머리 주석 '늑대 무리 협동 사냥', world.py `pack_goals`·`_pack_step`)
	// ------------------------------------------------------------------------------------------------------------

	// 늑대 하나의 이번 스텝 미리 보기 (이동 전)
	struct FPackWolf
	{
		double X = 0.0;             // 이동 전 위치·heading
		double Y = 0.0;
		double HeadX = 1.0;
		double HeadY = 0.0;
		bool bLeader = false;       // 앞장: 보통 위협 ∧ 전력 걸음 ∧ 표적 있음
		bool bHelper = false;       // 돕는 늑대 후보: 보통 위협 ∧ 사냥 중 ∧ 전력 걸음 아님
		std::int32_t Target = -1;   // 이번 스텝 표적 (앞장만 읽는다)
	};

	// 돕는 늑대 하나의 목표 (world.py `pack_goals` 의 한 행)
	struct FPackGoal
	{
		bool bHelp = false;         // 돕는다 (쫓기는 사슴을 골랐다)
		bool bWait = false;         // 목표 자리에 닿아 기다린다 (속력 0)
		bool bDoor = false;         // 목표 = 은신처 문 (아니면 도주선 앞)
		std::int32_t Prey = -1;     // 고른 쫓기는 사슴 (FPreyView 색인)
		double DirX = 0.0;          // 이동 방향 (단위. 기다림이면 사슴 쪽)
		double DirY = 0.0;
	};

	/**
	 * 늑대 하나의 이번 스텝 사냥·표적·전력 걸음을 상태 사본으로 미리 본다 (T 는 바꾸지 않는다). In 의 무리 칸·원거리 굴림은 지우고 부른다 —
	 * 표적·전력 걸음은 선회·굴림과 무관하다. 그래서 난수를 더 뽑지 않고, 본 스텝의 Step 결과와 같은 사냥·표적·전력 걸음이다.
	 */
	inline FPackWolf PackPeek(const FThreatSpec& Spec, const FThreatState& T, const FThreatStepInput& In, const FThreatConfig& Cfg)
	{
		FPackWolf P;
		P.X = T.PosX;
		P.Y = T.PosY;
		P.HeadX = T.HeadX;
		P.HeadY = T.HeadY;
		FThreatState Tmp = T;
		FThreatStepInput Pi = In;
		Pi.bPackHelp = false;
		Pi.bPackWait = false;
		Pi.RangedRoll = nullptr;
		const FThreatStepResult R = Step(Spec, Tmp, Pi, Cfg);
		const bool bWolf = Spec.Type != EThreatType::Player;
		P.bLeader = bWolf && R.bRunning && R.bHasTarget;
		P.bHelper = bWolf && R.bHunting && !R.bRunning;
		P.Target = R.Target;
		return P;
	}

	/**
	 * 돕는 늑대마다 목표 (world.py `pack_goals` 와 같은 순서·같은 식 — 골든 비트 동일). Covers = 은신처 원 (x, y, r) × NumCovers, r 은 사슴 반지름
	 * (r ≤ 0 은 지워진 은신처라 건너뛴다). WolfMargin = 늑대 몸 여유 (막지 않으면 0). Out[M] 을 모두 다시 쓴다.
	 *   쫓기는 사슴 = JoinR 안 앞장 표적 가운데 가장 가까운 것 (같으면 앞 슬롯 앞장). 도주 방향 U = 사슴 이동 단위벡터, 서 있으면 앞장 → 사슴.
	 *   문 = 0 < e_k ≤ DoorR ∧ (c_k − p)·U / |c_k − p| ≥ DoorCos 인 은신처 가운데 e_k = |c_k − p| − r_k 최소 (같으면 앞 번호) → c − (r + m)·(c − p)/|c − p|.
	 *   없으면 p + Lead·U. 무대 [0, WorldSize] 로 자른다. |G − q| ≤ WaitR 면 기다림(사슴 쪽, 겹치면 heading), 아니면 (G − q)/|G − q|.
	 */
	inline void PackGoals(const FPackWolf* Wolves, std::int32_t M, const FPreyView* Prey, std::int32_t NumPrey, const double* Covers,
						  std::int32_t NumCovers, double WolfMargin, double WorldSize, const FPackHuntConfig& Cfg, FPackGoal* Out)
	{
		for (std::int32_t m = 0; m < M; ++m)
		{
			Out[m] = FPackGoal();
		}
		if (!Cfg.bEnabled)
		{
			return;
		}
		for (std::int32_t m = 0; m < M; ++m)
		{
			const FPackWolf& Me = Wolves[m];
			if (!Me.bHelper)
			{
				continue;
			}
			std::int32_t Best = -1;
			std::int32_t BestL = -1;
			double BestD = 0.0;
			for (std::int32_t L = 0; L < M; ++L)
			{
				if (L == m || !Wolves[L].bLeader)
				{
					continue;
				}
				const std::int32_t I = Wolves[L].Target;
				if (I < 0 || I >= NumPrey)
				{
					continue;
				}
				const double Dx = Prey[I].X - Me.X;
				const double Dy = Prey[I].Y - Me.Y;
				const double D = std::sqrt(Dx * Dx + Dy * Dy);
				if (D <= Cfg.JoinR && (Best < 0 || D < BestD))
				{
					Best = I;
					BestL = L;
					BestD = D;
				}
			}
			if (Best < 0)
			{
				continue;
			}
			const FPreyView& P = Prey[Best];
			double Ux = 0.0;
			double Uy = 0.0;
			const double N = std::sqrt(P.MoveX * P.MoveX + P.MoveY * P.MoveY);
			if (N > kEps)
			{
				Ux = P.MoveX / N;
				Uy = P.MoveY / N;
			}
			else
			{
				const double Ax = P.X - Wolves[BestL].X;
				const double Ay = P.Y - Wolves[BestL].Y;
				const double Na = std::sqrt(Ax * Ax + Ay * Ay);
				if (Na > kEps)
				{
					Ux = Ax / Na;
					Uy = Ay / Na;
				}
			}
			std::int32_t Bk = -1;
			double Be = 0.0, Bex = 0.0, Bey = 0.0, Bdk = 0.0;
			for (std::int32_t k = 0; k < NumCovers; ++k)
			{
				const double R = Covers[3 * k + 2];
				if (!(R > 0.0))
				{
					continue;
				}
				const double Ex = Covers[3 * k] - P.X;
				const double Ey = Covers[3 * k + 1] - P.Y;
				const double Dk = std::sqrt(Ex * Ex + Ey * Ey);
				const double E = Dk - R;
				if (E > 0.0 && E <= Cfg.DoorR && (Ex * Ux + Ey * Uy) / Dk >= Cfg.DoorCos && (Bk < 0 || E < Be))
				{
					Bk = k;
					Be = E;
					Bex = Ex;
					Bey = Ey;
					Bdk = Dk;
				}
			}
			double Gx, Gy;
			if (Bk >= 0)
			{
				const double Rr = Covers[3 * Bk + 2] + WolfMargin;
				Gx = Covers[3 * Bk] - Rr * (Bex / Bdk);
				Gy = Covers[3 * Bk + 1] - Rr * (Bey / Bdk);
			}
			else
			{
				Gx = P.X + Cfg.Lead * Ux;
				Gy = P.Y + Cfg.Lead * Uy;
			}
			Gx = Gx < 0.0 ? 0.0 : (Gx > WorldSize ? WorldSize : Gx);
			Gy = Gy < 0.0 ? 0.0 : (Gy > WorldSize ? WorldSize : Gy);
			const double Hx = Gx - Me.X;
			const double Hy = Gy - Me.Y;
			const double Hn = std::sqrt(Hx * Hx + Hy * Hy);
			FPackGoal& G = Out[m];
			if (Hn <= Cfg.WaitR)
			{
				const double Fx = P.X - Me.X;
				const double Fy = P.Y - Me.Y;
				const double Fn = std::sqrt(Fx * Fx + Fy * Fy);
				G.DirX = Fn > kEps ? Fx / Fn : Me.HeadX;
				G.DirY = Fn > kEps ? Fy / Fn : Me.HeadY;
				G.bWait = true;
			}
			else
			{
				G.DirX = Hx / Hn;
				G.DirY = Hy / Hn;
			}
			G.bHelp = true;
			G.bDoor = Bk >= 0;
			G.Prey = Best;
		}
	}

	// 같은 스텝에 여러 위협이 같은 초식을 잡아도 사망은 한 번이다. 비명 점(M8)의 주인은 가장 낮은 위협 색인이다(world.py:2125-2132).
	// CaughtByThreat[m] = 위협 슬롯 m 의 Step 결과 Caught. OutCatcher[i] = 초식 i 를 잡은 가장 낮은 위협 색인 (없으면 -1).
	inline void ResolveCatches(const std::int32_t* CaughtByThreat, std::int32_t NumThreats, std::int32_t* OutCatcher,
							   std::int32_t NumPrey)
	{
		for (std::int32_t i = 0; i < NumPrey; ++i)
		{
			OutCatcher[i] = -1;
		}
		for (std::int32_t m = 0; m < NumThreats; ++m)
		{
			const std::int32_t i = CaughtByThreat[m];
			if (i >= 0 && i < NumPrey && OutCatcher[i] < 0)
			{
				OutCatcher[i] = m;
			}
		}
	}
}
