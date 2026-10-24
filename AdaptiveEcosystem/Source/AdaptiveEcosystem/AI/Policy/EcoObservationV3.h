// v3 관측 18 만들기와 개체 지각 기하 — 파이썬 herbivore_rl/env_v2/world.py `_obs_from`·`_geometry`·`daynight_phase` 와
// repertoire.obs_extra 의 거울 (R1b 두뇌, 관측 18 = v1 7 + 낮밤 2 + 레퍼토리 9. 경보 칸 alarm_heard 는 없다).
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.** `<cmath>`·`<cstdint>` 와 EcoRepertoire.h·EcoThreatModel.h(숲 시야 FoliageBlocked — 같은 엔진 무관 헤더)만 쓴다.
//
// 계약: AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 2절(관측), 2-3(기하), 7-6(어둠).
// 단위: 파이썬 단위 (1단위 = 200 cm, 1스텝 = 8/60 s). Mass 층이 cm 를 ÷ 200 해서 넘긴다.
//
// 두 층:
//   1) 지각 기하 (PerceiveThreats·PerceiveKin·PerceiveCover) — 개체 하나 대 위협·동족·은신처 목록. 목록 모으기
//      (이웃 격자, 생존 필터)는 Mass 층의 몫이다. 파이썬은 이번 스텝에 죽은 개체도 리스폰 전 관측의 동족에 넣는다
//      (계약 2-3 '사망 개체', 열린 질문 5) — 넣을지는 부르는 쪽이 정한다.
//   2) 관측 만들기 (BuildObservation) — 미리 계산한 기하·상태로 float 18칸. 모든 칸을 double 로 계산한 뒤 float 로 바꾼다
//      (파이썬 float64 → float32 배열). 같은 double 입력이면 파이썬과 비트 단위로 같다.
// 먹이 밀도(관측 0)와 먹이 기울기는 세계 격자 값이다(파이썬 21×21 셀 상자 평균, 계약 2-2 칸 0). 여기서는 입력으로 받는다.
//
// 언제 만드나 (계약 2-1): 스텝 끝 t + 1 → Tick → 새 t 의 어둠 → 기하 → Perceive(away·recency) → 관측 → 리스폰한 개체만 다시.
// Arbiter 는 float 관측이 아니라 같은 때의 기하(double)를 읽는다 — FThreatPerception 을 FDecisionObs 로 옮긴다(ToDecisionObs).
//
// R5 장애물 관측 (10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계약 2-4): 관측 21 두뇌는 18 칸 뒤에 세 칸을 더 받는다
// (escape_room·obstacle_near·threat_hidden — ObstacleObsValues·WriteObstacleObs). 관측 18 은 그대로이고, 세 칸은 따로 만든다 — 망 입력을 붙이는 것은
// 세계 층(EcoWorldV3::DecideHerb)의 몫이다. 파이썬 world.py `obstacle_obs_values` 와 같은 식·같은 순서라 같은 double 입력이면 비트 단위로 같다
// (골든 ObstacleObsGoldenVectorsV3.h, 시험 Policy.V3.ObstacleObs.*).
// 숲 시야 (10-21, world.py obstacles.foliage — 기본 끔): FObstacleObsInput::bFoliage 면 threat_hidden 의 가림 = 줄기 ∨ 잎(EcoThreatV3::FoliageBlocked,
// 위협 → 나 눈길 — 늑대 표적 고르기와 같은 판정). 끄면 위 그대로 (골든 FoliageGoldenVectorsV3.h, 시험 Policy.V3.Foliage.*).
// 두 길 두뇌 관측 24 (10-22 설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16-4, 이식 계획서 RL_V3_ROUTE_CPP_PORT_PLAN.md 3절): 관측 21 뒤 맨 끝 세 칸
// in_panic·shelter_reach·shelter_edge (kRouteObsNames — WriteRouteObs). 값은 스텝 끝 H 의 도주 반사 길 단계(EcoWorldV3 RouteStep)가 정하고 E 의 관측 18·21 은
// 건드리지 않는다(파이썬 `_obs_from` 도 이 세 칸을 0 으로 두고 `step` 이 `_wf_update` 뒤에 쓴다). 길 끈 두뇌(관측 18·21)는 이 칸을 읽지 않는다.

#pragma once

#include <cmath>
#include <cstdint>
#include <limits>

#include "EcoRepertoire.h"
#include "EcoThreatModel.h"

namespace EcoObservationV3
{
	using EcoRepertoireV3::FVec2;

	// ---- 관측 칸 (world.obs_names, R1b 18칸. EcoPolicyV3::kObsNames 와 같은 순서 — 자동화 시험이 확인한다) ----
	inline constexpr std::int32_t kObsDim = 18;
	inline constexpr std::int32_t kObsFoodDensity = 0;
	inline constexpr std::int32_t kObsPredCount = 1;
	inline constexpr std::int32_t kObsPredDist = 2;
	inline constexpr std::int32_t kObsKinCount = 3;
	inline constexpr std::int32_t kObsEnergy = 4;
	inline constexpr std::int32_t kObsRecentPredation = 5;
	inline constexpr std::int32_t kObsCoverDist = 6;
	inline constexpr std::int32_t kObsVisibility = 7;
	inline constexpr std::int32_t kObsToTransition = 8;
	inline constexpr std::int32_t kObsPredApproach = 9;
	inline constexpr std::int32_t kObsKinAlarm = 10;
	inline constexpr std::int32_t kObsBehGraze = 11;     // 11..15 지금 행동 원핫 (EcoRepertoireV3 행동 번호 순)
	inline constexpr std::int32_t kObsBehSteps = 16;
	inline constexpr std::int32_t kObsThreatRecency = 17;

	inline constexpr const char* kObsNames[kObsDim] = {
		"food_density", "pred_count", "pred_dist", "kin_count", "energy", "recent_predation", "cover_dist",
		"visibility", "to_transition", "pred_approach", "kin_alarm", "beh_graze", "beh_flee", "beh_hide",
		"beh_freeze", "beh_sleep", "beh_steps", "threat_recency"};

	/** 관측·지각 계수 (configs/default.yaml + v3_r1_on.yaml daynight·repertoire). 골든 상수 표와 시험이 비교한다. */
	struct FObservationConfig
	{
		double SeeR = 20.0;                         // 초식 시야 4000 cm (동족은 늘 이 반경)
		double FovCos = 0.5000000000000001;         // cos(radians(120) × 0.5) 의 float64 값 그대로
		double ObsPredCountNorm = 8.0;
		double ObsKinCountNorm = 20.0;
		double ObsCoverNorm = 20.0;                 // 4000 cm
		double MaxEnergy = 1.0;
		double DetectNight = 0.5;                   // 위협 탐지 반경 × (1 − 0.5·d), visibility = 1 − 0.5·d
		double TransitionNorm = 900.0;
		double HerbSpeed = 0.6;                     // 접근 관측의 분모 (단위/스텝)
		double SepRadius = 5.0;                     // 1000 cm
		double StepsNorm = 60.0;
		double PredationEmaDecay = 0.95;
		double PredationEmaGain = 10.0;
		// R3 감지 (파이썬 realism_vision·realism_hearing, 사람 결정 10-15 (7) 야생 1단계가 켠다). 기본 = R1b 학습 세계 그대로
		double ThreatFovCos = 0.5000000000000001;   // 위협 시야 문턱 cos (realism_vision threat_cos. 기본 = FovCos 와 같은 120°)
		bool bHearCapToSight = false;               // 들리는 반경을 이 사슴의 지금 탐지 반경으로 자르나 (cap_to_sight)
	};

	inline constexpr FObservationConfig kR1bObsConfig{};

	// ---- 어둠 (계약 7-6, world.daynight_phase) ----

	struct FDayNight
	{
		double Dark = 0.0;                    // d ∈ [0, 1]. 전환 스텝에 정확히 0.5
		std::int32_t StepsToTransition = 1;   // 다음 전환까지 남은 스텝 r ∈ [1, T/2]
	};

	/**
	 * 스텝 t 의 어둠과 남은 스텝. h = T/2, s = (t + o) mod T, e = s mod h, r = h − e, k = min(e, r), x = k ÷ (2τ).
	 * 낮(s < h) d = max(0.5 − x, 0), 밤 d = min(0.5 + x, 1). τ = 박명 폭(정수 스텝, 0.05·T). t·o 는 0 이상.
	 * C++ 꼴: e = Now − PhaseStart, r = PhaseEnd − Now. 낮 고정 세계는 부르지 않는다(d = 0, to_transition 1).
	 */
	inline FDayNight DayNightPhase(std::int64_t T, std::int32_t Period, std::int32_t Offset, std::int32_t TwilightSteps)
	{
		const std::int64_t H = Period / 2;
		const std::int64_t S = (T + Offset) % Period;
		const std::int64_t E = S % H;
		const std::int64_t R = H - E;
		const std::int64_t K = E < R ? E : R;
		const double X = static_cast<double>(K) / (2.0 * static_cast<double>(TwilightSteps));
		FDayNight Out;
		if (S >= H)
		{
			const double D = 0.5 + X;
			Out.Dark = D < 1.0 ? D : 1.0;
		}
		else
		{
			const double D = 0.5 - X;
			Out.Dark = D > 0.0 ? D : 0.0;
		}
		Out.StepsToTransition = static_cast<std::int32_t>(R);
		return Out;
	}

	/** visibility = 1 − detect_night·d (관측 7). */
	constexpr double Visibility(double Dark, const FObservationConfig& Cfg = kR1bObsConfig)
	{
		return 1.0 - Cfg.DetectNight * Dark;
	}

	/** 초식의 위협 탐지 기본 반경 see_r·visibility (world._see_pred). 행동 배수는 PerceiveThreats 가 곱한다. */
	constexpr double SeePredRadius(double Dark, const FObservationConfig& Cfg = kR1bObsConfig)
	{
		return Cfg.SeeR * Visibility(Dark, Cfg);
	}

	/** 전역 피식 EMA 갱신 (world.step 6): 0.95·ema + 0.05·(잡힌 수 ÷ N)·10. N 은 파이썬 128 고정(열린 질문 7). */
	constexpr double UpdatePredationEma(double Ema, std::int32_t NumCaught, std::int32_t NumAgents,
										const FObservationConfig& Cfg = kR1bObsConfig)
	{
		return Cfg.PredationEmaDecay * Ema
			   + (1.0 - Cfg.PredationEmaDecay) * (static_cast<double>(NumCaught) / static_cast<double>(NumAgents))
					 * Cfg.PredationEmaGain;
	}

	// ---- 지각 기하 (계약 2-3) ----

	/** 위협 하나 (파이썬 단위). Vel = 지난 스텝의 실제 변위(벽 자르기 포함, pred_vel). bAsleep = 굴에서 자는 주행성. */
	struct FThreatInput
	{
		double X = 0.0;
		double Y = 0.0;
		double VelX = 0.0;
		double VelY = 0.0;
		bool bAsleep = false;
		double HearR = 0.0;   // 발소리 반경 (realism_hearing, HearingRadius). 0 = 들리지 않음 (끈 세계는 늘 0)
		bool bHunting = true; // Social metadata only. Resting/eating wolves never raise a new threat alarm.
		// 세로 장애물 (야생 2단계 3, world.py sight_blocked): 이 사슴에서 이 위협까지의 눈길을 원판이 가린다. 참이면 눈으로 못 보고 발소리만 남는다.
		// EcoWorldV3 가 사슴마다 채운다 (끈 세계는 늘 거짓 — 지금 그대로)
		bool bOccluded = false;
	};

	/** R3 발소리 계수 (파이썬 realism_hearing, configs/v3_r3.yaml·v3_wild1_mirror.yaml 값). 기본 끔. */
	struct FHearingConfig
	{
		bool bEnabled = false;
		double SSilent = 0.05;      // 이 속력(× 사슴 걸음 HerbSpeed) 밑이면 소리 없음
		double SQuiet = 0.3;        // 이 속력 이하 반경 RQuiet
		double SLoud = 1.0;         // 이 속력 이상 반경 RLoud (사이는 선형)
		double RQuiet = 2.0;        // 4 m
		double RLoud = 20.0;        // 40 m
		bool bRoamQuiet = true;     // 전력 걸음이 아닌 위협(배회·잠행·쉼)은 속력을 SQuiet 에서 자른다
		bool bCapToSight = false;   // 들리는 반경을 탐지 반경으로 자르나
	};

	/**
	 * 위협의 소리 반경 (world.py hearing_radius). S = 지난 스텝 변위 크기 ÷ HerbSpeed, bRunning = 그 스텝이 전력 걸음
	 * (표적을 쫓는 추격형·잠행형 돌진·플레이어 돌진 — EcoThreatV3::FThreatStepResult::bRunning).
	 */
	inline double HearingRadius(const FHearingConfig& H, double S, bool bRunning)
	{
		const double S2 = (H.bRoamQuiet && !bRunning) ? (S < H.SQuiet ? S : H.SQuiet) : S;
		const double T0 = (S2 - H.SQuiet) / (H.SLoud - H.SQuiet);
		const double T = T0 < 0.0 ? 0.0 : (T0 > 1.0 ? 1.0 : T0);
		return S2 < H.SSilent ? 0.0 : H.RQuiet + (H.RLoud - H.RQuiet) * T;
	}

	/** 시야각(도) → 문턱 cos (world.py _fov_cos): 기본 시야각이면 기본 cos 그대로, 360° 이상이면 각도 판정 없음(−∞ 대신 −2). */
	inline double FovCosOf(double Deg, double BaseDeg, double BaseCos)
	{
		if (Deg == BaseDeg)
		{
			return BaseCos;
		}
		return Deg >= 360.0 ? -2.0 : std::cos(Deg * (3.141592653589793 / 180.0) * 0.5);
	}

	struct FThreatPerception
	{
		// Presentation metadata only: never appended to the 18 policy observations.
		bool bNearestSight = false;
		bool bNearestHeard = false;
		std::int32_t PredCount = 0;               // 보이는 위협 수 (관측 1, 결정 관측)
		double DPredMin = EcoRepertoireV3::kNoThreatDist;
		std::int32_t Nearest = -1;                // 가장 가까운 보이는 위협 (동점 낮은 색인)
		FVec2 AwayFromPred;                       // 그 반대 단위벡터, 안 보이면 0
		double PredApproach = 0.5;                // 접근 관측 (float64), 안 보이면 0.5
		std::int32_t PredCountEv = 0;             // 사건 비교 시야 (E1·E2 전용)
		double DPredMinEv = EcoRepertoireV3::kNoThreatDist;
		std::int32_t NearestEv = -1;
		double PredApproachEv = 0.5;
	};

	/** 접근 관측 c = −(v·e) ÷ |e| ÷ herb_speed, (clip(c, −1, 1) + 1) ÷ 2. e = 위협 − 나, Inv = 1 ÷ max(|e|, 1e-9). */
	inline double ApproachObs(double VelX, double VelY, double Ex, double Ey, double Inv,
							  const FObservationConfig& Cfg = kR1bObsConfig)
	{
		const double C = -(VelX * Ex + VelY * Ey) * Inv / Cfg.HerbSpeed;
		const double Cc = C < -1.0 ? -1.0 : (C > 1.0 ? 1.0 : C);
		return (Cc + 1.0) * 0.5;
	}

	/**
	 * 위협 지각 (world._geometry 포식자 줄). 보임 = 실거리 <= SeePred·SeeMult ∧ (e·H) × (1 ÷ max(d, 1e-9)) >= cos 60° ∧ 깨어 있음.
	 * 사건 비교 시야 = 보임 ∧ 실거리 <= SeePred·min(SeeMult, SeeMultLast).
	 * SeePred = SeePredRadius(d), SeeMult·SeeMultLast = FRepState 의 같은 칸(이번 스텝 제어기가 정한 배수와 직전 배수).
	 */
	inline FThreatPerception PerceiveThreats(const FVec2& Pos, const FVec2& Head, double SeePred, double SeeMult,
											 double SeeMultLast, const FThreatInput* Threats, std::int32_t NumThreats,
											 const FObservationConfig& Cfg = kR1bObsConfig)
	{
		FThreatPerception R;
		const double SeeP = SeePred * SeeMult;
		const double Lo = SeeMult < SeeMultLast ? SeeMult : SeeMultLast;
		const double SeeEv = SeePred * Lo;
		double BestEx = 0.0, BestEy = 0.0, BestInv = 0.0;
		double BestEvEx = 0.0, BestEvEy = 0.0, BestEvInv = 0.0;
		for (std::int32_t m = 0; m < NumThreats; ++m)
		{
			const FThreatInput& T = Threats[m];
			const double Ex = T.X - Pos.X;
			const double Ey = T.Y - Pos.Y;
			const double Pd = std::sqrt(Ex * Ex + Ey * Ey);
			const double Inv = 1.0 / (Pd > EcoRepertoireV3::kEps ? Pd : EcoRepertoireV3::kEps);
			// 보임: 시야(반경 SeeP, 위협 시야각 ThreatFovCos, 원판에 가리지 않음) 또는 발소리(실거리 ≤ HearR, 방향 무관 — realism_hearing). 자는 위협은 빠진다
			const bool bSight = !T.bOccluded && Pd <= SeeP && (Ex * Head.X + Ey * Head.Y) * Inv >= Cfg.ThreatFovCos;
			const double HearLim = Cfg.bHearCapToSight ? (T.HearR < SeeP ? T.HearR : SeeP) : T.HearR;
			const bool bHeard = T.HearR > 0.0 && Pd <= HearLim;
			const bool bVis = (bSight || bHeard) && !T.bAsleep;
			if (!bVis)
			{
				continue;
			}
			++R.PredCount;
			if (R.Nearest < 0 || Pd < R.DPredMin)
			{
				R.Nearest = m;
				R.bNearestSight = bSight;
				R.bNearestHeard = bHeard;
				R.DPredMin = Pd;
				BestEx = Ex;
				BestEy = Ey;
				BestInv = Inv;
			}
			if (Pd <= SeeEv)
			{
				++R.PredCountEv;
				if (R.NearestEv < 0 || Pd < R.DPredMinEv)
				{
					R.NearestEv = m;
					R.DPredMinEv = Pd;
					BestEvEx = Ex;
					BestEvEy = Ey;
					BestEvInv = Inv;
				}
			}
		}
		if (R.Nearest >= 0)
		{
			R.AwayFromPred = {-BestEx * BestInv, -BestEy * BestInv};
			const FThreatInput& T = Threats[R.Nearest];
			R.PredApproach = ApproachObs(T.VelX, T.VelY, BestEx, BestEy, BestInv, Cfg);
		}
		if (R.NearestEv >= 0)
		{
			const FThreatInput& T = Threats[R.NearestEv];
			R.PredApproachEv = ApproachObs(T.VelX, T.VelY, BestEvEx, BestEvEy, BestEvInv, Cfg);
		}
		return R;
	}

	/** 동족 하나. Behavior = 지금 행동(이번 스텝에 실행한 행동 — kin_alarm 이 FLEE 를 센다). */
	struct FKinInput
	{
		double X = 0.0;
		double Y = 0.0;
		std::int32_t Behavior = EcoRepertoireV3::kGraze;
	};

	struct FKinPerception
	{
		std::int32_t KinCount = 0;     // 보이는 동족 수 (관측 3)
		std::int32_t FleeCount = 0;    // 그중 FLEE
		FVec2 ToCentroid;              // normalize(보이는 동족 위치 평균 − P), 없으면 0
		FVec2 Separation;              // −Σ w (pos_j − P)/d 를 크기 1로 자른 값 (시야각 없음, 자기 제외)
		double KinAlarm = 0.0;         // FleeCount ÷ KinCount, 없으면 0 (관측 10)
	};

	/**
	 * 동족 지각 (world._geometry 동족·분리 줄). Agents 는 자기(Self)를 포함한 목록이고 Self 는 건너뛴다.
	 * 보임 = 실거리 <= see_r(20, 밤·행동 배수 없음) ∧ 시야각 120°. 같은 좌표(거리 0)인 동족은 내적 0 이라 보이지 않는다.
	 * 분리는 파이썬과 같은 꼴 Σc·pos − (Σc)·P 로 더한다(c = max(1 − d/5, 0) ÷ max(d, 1e-9)). 합(SumX·CX·CSum)은 j 차례 —
	 * 파이썬 world.py `_seq_sum` 도 10-22 부터 같은 차례라 비트 단위로 같다(그 전 행렬곱은 끝 비트가 달랐다).
	 */
	inline FKinPerception PerceiveKin(std::int32_t Self, const FVec2& Pos, const FVec2& Head, const FKinInput* Agents,
									  std::int32_t NumAgents, const FObservationConfig& Cfg = kR1bObsConfig)
	{
		FKinPerception R;
		double SumX = 0.0, SumY = 0.0;
		double CX = 0.0, CY = 0.0, CSum = 0.0;
		for (std::int32_t j = 0; j < NumAgents; ++j)
		{
			if (j == Self)
			{
				continue;
			}
			const FKinInput& A = Agents[j];
			const double Dx = A.X - Pos.X;
			const double Dy = A.Y - Pos.Y;
			const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
			const double Invd = 1.0 / (Dist > EcoRepertoireV3::kEps ? Dist : EcoRepertoireV3::kEps);
			if (Dist <= Cfg.SeeR && (Dx * Head.X + Dy * Head.Y) * Invd >= Cfg.FovCos)
			{
				++R.KinCount;
				SumX += A.X;
				SumY += A.Y;
				R.FleeCount += A.Behavior == EcoRepertoireV3::kFlee ? 1 : 0;
			}
			const double Wgt = 1.0 - Dist / Cfg.SepRadius;
			const double C = (Wgt > 0.0 ? Wgt : 0.0) * Invd;
			CX += C * A.X;
			CY += C * A.Y;
			CSum += C;
		}
		if (R.KinCount > 0)
		{
			const double Den = static_cast<double>(R.KinCount);
			R.ToCentroid = EcoRepertoireV3::Normalize({SumX / Den - Pos.X, SumY / Den - Pos.Y});
			R.KinAlarm = static_cast<double>(R.FleeCount) / Den;
		}
		R.Separation = EcoRepertoireV3::ClampMagnitude({-(CX - CSum * Pos.X), -(CY - CSum * Pos.Y)}, 1.0);
		return R;
	}

	/** 은신처 원 하나 (파이썬 단위). */
	struct FCoverInput
	{
		double X = 0.0;
		double Y = 0.0;
		double Radius = 0.0;
	};

	struct FCoverPerception
	{
		std::int32_t CoverK = -1;                         // 가장자리 거리 argmin (동점 낮은 색인), 없으면 -1
		double Edge = EcoRepertoireV3::kNoThreatDist;     // 가장자리까지 거리 = 중심 거리 − 반지름 (안이면 <= 0)
		bool bInCover = false;                            // Edge <= 0 (경계 포함)
		double CoverDist = 1.0;                           // clip(max(e, 0) ÷ 20, 0, 1), 은신처가 없으면 1 (관측 6)
	};

	inline FCoverPerception PerceiveCover(const FVec2& Pos, const FCoverInput* Covers, std::int32_t NumCovers,
										  const FObservationConfig& Cfg = kR1bObsConfig)
	{
		FCoverPerception R;
		for (std::int32_t k = 0; k < NumCovers; ++k)
		{
			if(Covers[k].Radius<=0)continue; // Stable-index tombstone of an unregistered refuge.
			const double Dx = Covers[k].X - Pos.X;
			const double Dy = Covers[k].Y - Pos.Y;
			const double E = std::sqrt(Dx * Dx + Dy * Dy) - Covers[k].Radius;
			if (R.CoverK < 0 || E < R.Edge)
			{
				R.CoverK = k;
				R.Edge = E;
			}
		}
		if (R.CoverK >= 0)
		{
			R.bInCover = R.Edge <= 0.0;
			const double C = (R.Edge > 0.0 ? R.Edge : 0.0) / Cfg.ObsCoverNorm;
			R.CoverDist = C < 0.0 ? 0.0 : (C > 1.0 ? 1.0 : C);
		}
		return R;
	}

	/**
	 * 지각 결과 + 지금 에너지·어둠 -> 다음 스텝 Arbiter 의 결정 관측 (world._rep_decision_obs).
	 * Energy01 = clip(E ÷ MaxEnergy, 0, 1). Dark 는 새 t 의 d (다음 스텝 동역학이 쓰는 값).
	 */
	inline EcoRepertoireV3::FDecisionObs ToDecisionObs(const FThreatPerception& T, const FCoverPerception& C,
													   double Energy01, double Dark)
	{
		EcoRepertoireV3::FDecisionObs O;
		O.PredCount = T.PredCount;
		O.DPredMin = T.DPredMin;
		O.PredApproach = T.PredApproach;
		O.PredCountEv = T.PredCountEv;
		O.DPredMinEv = T.DPredMinEv;
		O.PredApproachEv = T.PredApproachEv;
		O.Energy = Energy01;
		O.Dark = Dark;
		O.bInCover = C.bInCover;
		O.CoverK = C.CoverK;
		return O;
	}

	// ---- 관측 18 (계약 2-2, world._obs_from + repertoire.obs_extra) ----

	/** 관측 입력 (스텝 끝 값). 거리·반경은 파이썬 단위. */
	struct FObservationInput
	{
		double FoodDensity = 0.0;            // 0  위치 셀의 먹이 상자 평균 (세계 격자)
		std::int32_t PredCount = 0;          // 1  보이는 위협 수
		double DPredMin = EcoRepertoireV3::kNoThreatDist;   // 2  PredCount > 0 일 때만 읽는다
		std::int32_t KinCount = 0;           // 3
		double Energy = 0.5;                 // 4  E (MaxEnergy 로 나눈다)
		double PredEma = 0.0;                // 5  전역 피식 EMA
		bool bHasCover = false;              // 6  세계에 은신처가 있나
		double CoverEdge = 0.0;              //    가장 가까운 은신처 가장자리 거리 (FCoverPerception::Edge)
		double Dark = 0.0;                   // 7  d (낮 고정 세계는 0)
		double VisMult = 1.0;                //    visibility 날씨 배수 w (야생 3단계 — EcoWorldV3 ObsVisibilityMult). 1 = 지금 그대로
		std::int32_t StepsToTransition = 1;  // 8  r. 음수면 낮 고정 세계 (to_transition 1)
		double PredApproach = 0.5;           // 9
		double KinAlarm = 0.0;               // 10
		std::int32_t Behavior = EcoRepertoireV3::kGraze;   // 11..15
		std::int32_t StepsIn = 0;            // 16 tick 뒤 값 (FRepState::StepsIn)
		double Recency = 0.0;                // 17 Perceive 뒤 값 (FRepState::Recency)
	};

	namespace Detail
	{
		constexpr double Clip01(double X) { return X < 0.0 ? 0.0 : (X > 1.0 ? 1.0 : X); }
		constexpr double Min1(double X) { return X < 1.0 ? X : 1.0; }
	}

	/** 관측 18칸 (float). 순서·정규화·자르기는 계약 2-2 표 그대로다. */
	inline void BuildObservation(const FObservationInput& In, float Out[kObsDim],
								 const FObservationConfig& Cfg = kR1bObsConfig)
	{
		Out[kObsFoodDensity] = static_cast<float>(Detail::Clip01(In.FoodDensity));
		Out[kObsPredCount] = static_cast<float>(Detail::Clip01(static_cast<double>(In.PredCount) / Cfg.ObsPredCountNorm));
		Out[kObsPredDist] = In.PredCount > 0 ? static_cast<float>(Detail::Clip01(In.DPredMin / Cfg.SeeR)) : 1.0f;
		Out[kObsKinCount] = static_cast<float>(Detail::Clip01(static_cast<double>(In.KinCount) / Cfg.ObsKinCountNorm));
		Out[kObsEnergy] = static_cast<float>(Detail::Clip01(In.Energy / Cfg.MaxEnergy));
		Out[kObsRecentPredation] = static_cast<float>(Detail::Min1(In.PredEma));
		Out[kObsCoverDist] = In.bHasCover
								 ? static_cast<float>(Detail::Clip01((In.CoverEdge > 0.0 ? In.CoverEdge : 0.0) / Cfg.ObsCoverNorm))
								 : 1.0f;
		// 계획서 RL_V2_PLAN.md 4.2 표 9: visibility = (1 − 0.5·d)·w. 날씨 w = 1 이면 곱해도 같은 값이다 (world.py `_vis` = (1 − x·d) × w_s)
		Out[kObsVisibility] = static_cast<float>(Visibility(In.Dark, Cfg) * In.VisMult);
		Out[kObsToTransition] = In.StepsToTransition < 0
									? 1.0f
									: static_cast<float>(Detail::Min1(static_cast<double>(In.StepsToTransition) / Cfg.TransitionNorm));
		Out[kObsPredApproach] = static_cast<float>(In.PredApproach);
		Out[kObsKinAlarm] = static_cast<float>(In.KinAlarm);
		for (std::int32_t b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
		{
			Out[kObsBehGraze + b] = b == In.Behavior ? 1.0f : 0.0f;
		}
		Out[kObsBehSteps] = static_cast<float>(Detail::Min1(static_cast<double>(In.StepsIn) / Cfg.StepsNorm));
		Out[kObsThreatRecency] = static_cast<float>(In.Recency);
	}

	// ---- R5 장애물 관측 세 칸 (계약 2-4, world.py 'R5 장애물 관측'·obstacle_obs_values) ----
	//
	// 관측 21 계약 = 관측 18 + 맨 끝 세 칸 (마스크 판 2 그대로, 계약 해시 EcoPolicyV3::kContractHashObs21Mask2). 칸 번호 18·19·20.
	inline constexpr std::int32_t kNumObstacleObs = 3;
	inline constexpr std::int32_t kObsDimObstacle = kObsDim + kNumObstacleObs;   // 21
	inline constexpr std::int32_t kObsEscapeRoom = 18;
	inline constexpr std::int32_t kObsObstacleNear = 19;
	inline constexpr std::int32_t kObsThreatHidden = 20;
	inline constexpr const char* kObstacleObsNames[kNumObstacleObs] = {"escape_room", "obstacle_near", "threat_hidden"};

	// ---- 두 길 두뇌 관측 세 칸 (관측 24 = 관측 21 + 맨 끝 세 칸 — world.py ROUTE_OBS_NAMES·`_route_step` 의 r_obs, 이식 계획서 3절) ----
	// 계약 해시 EcoPolicyV3::kContractHashObs24Mask4 (마스크 판 4)·kContractHashObs24Mask5 (판 5 = 판 4 + 반사 밖 두뇌 FLEE 막음). 칸 번호 21·22·23.
	// 망 입력 = [관측 18 | 장애물 세 칸 | 이 세 칸] (EcoWorldV3::DecideHerb)
	inline constexpr std::int32_t kNumRouteObs = 3;
	inline constexpr std::int32_t kObsDimRoute = kObsDimObstacle + kNumRouteObs;   // 24
	inline constexpr std::int32_t kObsInPanic = 21;          // 다음 스텝 덮기가 도주면 1
	inline constexpr std::int32_t kObsShelterReach = 22;     // SHELTER 가 가능하면 clip(μ* / 10, 0, 1) ∈ [0.2, 1], 아니면 0
	inline constexpr std::int32_t kObsShelterEdge = 23;      // SHELTER 가 가능하면 clip(e* / 20, 0, 1) ∈ (0, 1], 아니면 0
	inline constexpr const char* kRouteObsNames[kNumRouteObs] = {"in_panic", "shelter_reach", "shelter_edge"};
	inline constexpr double kRouteShelterReachNorm = 10.0;   // world.py ROUTE_SHELTER_REACH_U (단위 — 20 m)
	inline constexpr double kRouteShelterEdgeNorm = 20.0;    // world.py ROUTE_SHELTER_EDGE_NORM_U (단위 — 40 m)
	inline constexpr std::int32_t kMaxObsDim = kObsDimRoute;                     // 관측 칸 수 상한 (관측 18·21·24)
	static_assert(kObsInPanic == kObsDimObstacle && kObsShelterEdge == kObsDimRoute - 1, "길 관측 세 칸은 관측 21 바로 뒤 맨 끝이다");

	/** 분모 (configs/v3_wild3_obs_mirror.yaml obstacle_obs — R5 판, results/v3/r5/obs_check.md). 계약 해시 밖이라 골든 설정 칸이 지킨다. */
	struct FObstacleObsConfig
	{
		double EscapeNorm = 10.0;   // escape_room 분모 (단위, 20 m)
		double NearNorm = 5.0;      // obstacle_near 분모 (단위, 10 m)
	};

	inline constexpr FObstacleObsConfig kR5ObstacleObsConfig{};

	/** 사슴 하나의 입력 (스텝 끝 기하 — 이동 뒤 자리, 같은 관측의 위협 지각). 원판 (x, y, r) × NumDiscs, 무대 [0, StageSize]². */
	struct FObstacleObsInput
	{
		FVec2 Pos;
		FVec2 Head;
		bool bSeen = false;             // 위협을 아나 (관측 1 의 보임 — PredCount > 0)
		FVec2 Away;                     // 가장 가까운 보이는 위협의 반대 단위벡터 (FThreatPerception::AwayFromPred, 모르면 0)
		FVec2 Threat;                   // 그 위협의 자리 (bSeen 일 때만 읽는다)
		const double* Discs = nullptr;
		std::int32_t NumDiscs = 0;
		double BodyR = 0.0;             // 몸 반지름 (이동이 멈추는 반지름 = r + BodyR)
		double StageSize = 0.0;
		bool bBlockSight = false;       // 원판이 눈길을 가리나 (obstacles.block_sight)
		// 숲 시야 (10-21, obstacles.foliage): 참이면 가림 = 줄기 ∨ 잎 (원판 가운데 나무인 것 — FoliageTrees[k] ≠ 0, nullptr = 모두 — 의 중심에 반지름 FoliageR,
		// 눈길이 그 합집합 안을 FoliageBlock 이상 지나면). bBlockSight 일 때만 읽는다. 거짓(기본) = 줄기만
		bool bFoliage = false;
		const std::uint8_t* FoliageTrees = nullptr;
		double FoliageR = 0.0;
		double FoliageBlock = 0.0;
	};

	/** 원시 거리 (double). Near 는 원판이 없으면 +∞. */
	struct FObstacleObs
	{
		double Escape = 0.0;            // E 도망칠 쪽으로 곧장 갈 때 처음 막히는 거리 (벽·원판)
		double Near = std::numeric_limits<double>::infinity();   // N 몸 가장자리에서 가장 가까운 원판 가장자리까지 (원판 안이면 음수)
		bool bThreatHidden = false;     // 가장 가까운 보이는 위협 → 나 선분을 줄기(r)가 가린다
	};

	/**
	 * world.py `obstacle_obs_values` 의 C++ 꼴 (사슴 하나, 원판 순서대로, double — 줄마다 같은 식):
	 *   W = (bSeen ∧ |Away| > 1e-9) ? Away : Head; n = |W|; U = n > 1e-9 ? W ÷ n : (1, 0)
	 *   벽: Tx = Ux > 0 ? (S − x) ÷ Ux : (Ux < 0 ? x ÷ (−Ux) : ∞), Ty 같음, E = min(Tx, Ty), 0 보다 크지 않으면 0
	 *   원판 k (R = r + BodyR): F = P − c, Cc = F·F − R², B = F·U, Δ = B² − Cc. Cc ≥ 0 ∧ B < 0 ∧ Δ ≥ 0 이면 E = min(E, −B − √Δ)
	 *                          (원판 안에서 시작하면 건너뛴다·접함은 막는다 — 이동 obstacle_slide 와 같다). N = min(N, |F| − R)
	 *   가림: bSeen ∧ bBlockSight 이면 위협 a → 나 q 선분 (EcoThreatV3::SightBlocked 와 같은 식, 반지름 r — 몸 없음, 엄격한 <)
	 *         숲 시야(bFoliage)면 줄기가 안 가릴 때 잎도 본다 (EcoThreatV3::FoliageBlocked — world.py `obstacle_obs_values` 의 foliage 줄)
	 */
	inline FObstacleObs ObstacleObsValues(const FObstacleObsInput& In)
	{
		const double Inf = std::numeric_limits<double>::infinity();
		const double Eps = EcoRepertoireV3::kEps;
		double Wx = In.Head.X;
		double Wy = In.Head.Y;
		if (In.bSeen && std::sqrt(In.Away.X * In.Away.X + In.Away.Y * In.Away.Y) > Eps)
		{
			Wx = In.Away.X;
			Wy = In.Away.Y;
		}
		const double Nw = std::sqrt(Wx * Wx + Wy * Wy);
		const double Ux = Nw > Eps ? Wx / Nw : 1.0;
		const double Uy = Nw > Eps ? Wy / Nw : 0.0;
		const double X = In.Pos.X;
		const double Y = In.Pos.Y;
		const double S = In.StageSize;
		const double Tx = Ux > 0.0 ? (S - X) / Ux : (Ux < 0.0 ? X / (-Ux) : Inf);
		const double Ty = Uy > 0.0 ? (S - Y) / Uy : (Uy < 0.0 ? Y / (-Uy) : Inf);
		FObstacleObs R;
		R.Escape = Tx < Ty ? Tx : Ty;
		if (!(R.Escape > 0.0))
		{
			R.Escape = 0.0;
		}
		R.Near = Inf;
		const double* D = In.Discs;
		for (std::int32_t k = 0; k < In.NumDiscs; ++k)
		{
			const double Fx = X - D[3 * k];
			const double Fy = Y - D[3 * k + 1];
			const double Rk = D[3 * k + 2] + In.BodyR;
			const double Cc = Fx * Fx + Fy * Fy - Rk * Rk;
			const double Bb = Fx * Ux + Fy * Uy;
			const double Dd = Bb * Bb - Cc;
			if (Cc >= 0.0 && Bb < 0.0 && Dd >= 0.0)
			{
				const double T = -Bb - std::sqrt(Dd);
				R.Escape = T < R.Escape ? T : R.Escape;
			}
			const double Nk = std::sqrt(Fx * Fx + Fy * Fy) - Rk;
			R.Near = Nk < R.Near ? Nk : R.Near;
		}
		if (In.bSeen && In.bBlockSight)
		{
			const double Jx = In.Threat.X;
			const double Jy = In.Threat.Y;
			const double Dx = X - Jx;
			const double Dy = Y - Jy;
			const double DD = Dx * Dx + Dy * Dy;
			for (std::int32_t k = 0; k < In.NumDiscs && !R.bThreatHidden; ++k)
			{
				const double Gx = D[3 * k] - Jx;
				const double Gy = D[3 * k + 1] - Jy;
				double T = DD > 0.0 ? (Gx * Dx + Gy * Dy) / DD : 0.0;
				T = T < 0.0 ? 0.0 : (T > 1.0 ? 1.0 : T);
				const double Qx = Jx + T * Dx - D[3 * k];
				const double Qy = Jy + T * Dy - D[3 * k + 1];
				R.bThreatHidden = Qx * Qx + Qy * Qy < D[3 * k + 2] * D[3 * k + 2];
			}
			if (!R.bThreatHidden && In.bFoliage && In.NumDiscs > 0)
			{
				R.bThreatHidden = EcoThreatV3::FoliageBlocked(Jx, Jy, X, Y, D, In.NumDiscs, In.FoliageTrees, In.FoliageR, In.FoliageBlock);
			}
		}
		return R;
	}

	/** 관측 세 칸 (float): clip(E ÷ EscapeNorm, 0, 1), clip(max(N, 0) ÷ NearNorm, 0, 1) (원판 없음 = 1), 가림 0/1. world.py `_obs_from` 과 같다. */
	inline void WriteObstacleObs(const FObstacleObs& V, float Out[kNumObstacleObs], const FObstacleObsConfig& Cfg = kR5ObstacleObsConfig)
	{
		Out[0] = static_cast<float>(Detail::Clip01(V.Escape / Cfg.EscapeNorm));
		Out[1] = static_cast<float>(Detail::Clip01((V.Near > 0.0 ? V.Near : 0.0) / Cfg.NearNorm));
		Out[2] = V.bThreatHidden ? 1.0f : 0.0f;
	}

	// 두 길 두뇌 관측 세 칸 (world.py `_route_step` 의 r_obs — 이식 계획서 3절): 도주 ? (1, 가능 ? (float)clip(Mu / 10) : 0, 가능 ? (float)clip(E / 20) : 0) : 0
	// (Mu = 경주 여유 μ*, E = 가장자리 거리 e*). double 로 나누고(역수 곱 아님) 자른 뒤 float 로 내린다(가까운 짝수 — 파이썬 float64 → float32 배열 대입).
	// μ* = +∞(가까운 늑대 없음)는 1.
	inline void WriteRouteObs(bool bPanic, bool bOk, double Mu, double E, float Out[kNumRouteObs])
	{
		Out[0] = bPanic ? 1.0f : 0.0f;
		Out[1] = (bPanic && bOk) ? static_cast<float>(Detail::Clip01(Mu / kRouteShelterReachNorm)) : 0.0f;
		Out[2] = (bPanic && bOk) ? static_cast<float>(Detail::Clip01(E / kRouteShelterEdgeNorm)) : 0.0f;
	}
}
