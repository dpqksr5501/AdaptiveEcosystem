// v3 관측 18 만들기와 개체 지각 기하 — 파이썬 herbivore_rl/env_v2/world.py `_obs_from`·`_geometry`·`daynight_phase` 와
// repertoire.obs_extra 의 거울 (R1b 두뇌, 관측 18 = v1 7 + 낮밤 2 + 레퍼토리 9. 경보 칸 alarm_heard 는 없다).
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.** `<cmath>`·`<cstdint>` 와 EcoRepertoire.h 만 쓴다.
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

#pragma once

#include <cmath>
#include <cstdint>

#include "EcoRepertoire.h"

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
	};

	struct FThreatPerception
	{
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
			const bool bVis = Pd <= SeeP && (Ex * Head.X + Ey * Head.Y) * Inv >= Cfg.FovCos && !T.bAsleep;
			if (!bVis)
			{
				continue;
			}
			++R.PredCount;
			if (R.Nearest < 0 || Pd < R.DPredMin)
			{
				R.Nearest = m;
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
	 * 분리는 파이썬 행렬 꼴 Σc·pos − (Σc)·P 로 더한다(c = max(1 − d/5, 0) ÷ max(d, 1e-9)).
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
		Out[kObsVisibility] = static_cast<float>(Visibility(In.Dark, Cfg));
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
}
