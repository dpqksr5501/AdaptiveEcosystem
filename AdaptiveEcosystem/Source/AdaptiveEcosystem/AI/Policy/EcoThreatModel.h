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
// 잠행-돌진형 (world.py:2299-2313, 2353-2368): 표적 체감 거리 ≤ 6 이면 돌진 시작(남은 12). 남은 > 0 이면 돌진(× 1.5,
// 표적 있으면 표적 쪽, 없으면 head), 남은 ≤ 0 이면 마지막 판정 스텝(× 0.2, head). 돌진 이동 12번 + 마지막 판정 1번이고,
// 마지막 판정에서 놓치면 탈진 30스텝(× 0.2 배회, 사냥 안 함), 돌진·마지막 판정 중 잡으면 곧바로 ROAM 이다.
// 표적이 없는 ROAM 은 잠행 속력이 아니라 **기본 속력**으로 배회한다(계약 13-1 D3).
//
// 플레이어 대역 (world.py:2314-2336, 2379-2394): 배회(× 0.4, 배회 선회) · 잠행(× 0.3, 가장 가까운 체감 거리 개체 쪽,
// 체감 ≤ 6 이면 돌진 시작) · 돌진(× 1.3 으로 20번 이동, 남은 ≤ 0 이면 멈춘 판정 스텝) · 휴식(멈춤, 사냥 안 함, 30스텝).
// 배회·잠행 모드도 닿으면 잡는다. 돌진 중 잡거나 돌진이 끝나면 휴식. 휴식·배회·잠행 길이가 끝나면 새 모드
// (u0 < 0.5 면 잠행, 아니면 배회. 길이 = 200 + ⌊u1·201⌋, 400 에서 자른다).
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
	};

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
		bool bAsleep = false;       // 이번 스텝에 잤다. 초식 관측의 '자는 위협은 안 보인다'는 관측 때의 d 로 IsAsleep 을 다시 부른다
		std::int32_t Target = -1;   // 이번 스텝 표적 (FPreyView 색인, 없으면 -1). 애니메이션 시선용
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

		// 2. 쿨다운·잠·사냥 (world.py:2034-2037)
		T.Cooldown = T.Cooldown - 1 > 0 ? T.Cooldown - 1 : 0;
		const bool bAsleep = IsAsleep(Spec, In.Dark, Cfg);
		bool bHunting = T.Cooldown == 0 && !bAsleep;

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
				if (!P.bAlive)
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

		// 7. 밤잠·박명 (world.py:2078-2080)
		if (bAsleep)
		{
			MX = HX;
			MY = HY;
		}
		Speed = Speed * SpeedMult(Spec, In.Dark, Cfg);

		// 8. 이동·벽 반사·heading·변위 (world.py:2083-2113)
		double NX = QX + MX * Speed;
		double NY = QY + MY * Speed;
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
		Normalize2(MX, MY);
		T.HeadX = MX;
		T.HeadY = MY;
		T.VelX = NX - QX;
		T.VelY = NY - QY;
		T.PosX = NX;
		T.PosY = NY;

		// 9. 포획 (world.py:2115-2125, 2138-2141). 거리는 위협 이동 전 위치로 잰 1 의 값이다
		std::int32_t K = -1;
		double KD = 0.0;
		if (bHunting)
		{
			for (std::int32_t i = 0; i < In.NumPrey; ++i)
			{
				const FPreyView& P = In.Prey[i];
				if (!P.bAlive)
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

		T.bAsleep = bAsleep;
		T.Target = J;
		R.bAsleep = bAsleep;
		R.bHunting = bHunting;
		R.bHasTarget = bHasTarget;
		R.Target = J;
		R.TargetPerceived = bHasTarget ? DT : -1.0;
		R.Caught = K;
		R.Speed = Speed;
		return R;
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
