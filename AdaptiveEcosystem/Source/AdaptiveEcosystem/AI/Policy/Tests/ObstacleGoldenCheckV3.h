// v3 야생 2단계 3 세로 장애물 골든 대조 — EcoThreatModel.h (ObstacleSlide·SightBlocked·InsideAnyObstacle·Step 의 표적 가림과 이동)·
// EcoWorldV3.h (FObstacleConfig·ObstaclePushOut·FFoodGrid::ApplyObstacleFood)를 ObstacleGoldenVectorsV3.h (herbivore_rl/export_golden_v3_obstacle.py,
// 세계 configs/v3_wild2_obstacle_mirror.yaml)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<vector>` 와 엔진 무관 v3 세계 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoObstacleV3Test.cpp (AdaptiveEcosystem.Policy.V3.Obstacle.*)
//   g++ 하네스       herbivore_rl/tests/cpp/obstacle_v3_main.cpp (herbivore_rl/tests/test_wild2_obstacle.py)
// 모든 칸이 비트 단위로 같아야 한다(실수도 == — 파이썬과 같은 순서로 계산한다).
//
// 칸 번호 (FReport::FirstField):
//   미끄러짐 0 x, 1 y, 2 부딪힘, 3 물러남      시선 5 가림      먹이 6 용량      밀어내기 7 x, 8 y, 9 결과
//   스텝     10 위치 x, 11 위치 y, 12 heading x, 13 heading y, 14 쿨다운, 15 배부름, 16 잠행 상태, 17 남은 수, 18 돕기, 19 표적, 20 잡은 사슴,
//            21 원판 부딪힘, 22 되돌림, 23 돌아섬
//   설정     30 몸 반지름, 31 눈길 가림, 32 먹이 줄임, 33 기본 끔, 34 되풀이 수, 35 여유, 36 표본 수

#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

#include "../EcoWorldV3.h"
#include "../ObstacleGoldenVectorsV3.h"

namespace EcoWorldV3::ObstacleCheck
{
	namespace G = EcoWorldV3::GoldenObstacle;
	namespace T3 = EcoThreatV3;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int32_t Count0 = 0;       // 묶음마다 C++ 이 낸 수 (골든 합과 견준다): 미끄러짐 부딪힘·시선 가림·밀어내기 옮김·스텝 부딪힘
		std::int32_t Count1 = 0;       // 미끄러짐 물러남·밀어내기 못 옮김·스텝 돌아섬
		std::int32_t Count2 = 0;       // 스텝 포획

		bool Passed() const { return Failures == 0 && Cases > 0; }
	};

	namespace Detail
	{
		struct FCase
		{
			std::int32_t Field = -1;

			void Int(std::int32_t Id, std::int64_t Got, std::int64_t Want)
			{
				if (Got != Want && Field < 0)
				{
					Field = Id;
				}
			}

			void Real(std::int32_t Id, double Got, double Want)
			{
				if (!(Got == Want) && Field < 0)
				{
					Field = Id;
				}
			}
		};

		inline void Close(FReport& R, std::int32_t CaseId, const FCase& C)
		{
			++R.Cases;
			if (C.Field >= 0)
			{
				++R.Failures;
				if (R.FirstCase < 0)
				{
					R.FirstCase = CaseId;
					R.FirstField = C.Field;
				}
			}
		}

		inline const double* SetDiscs(std::int32_t Set, std::int32_t& OutNum)
		{
			OutNum = G::kSetIndex[2 * Set + 1];
			return G::kSetDiscs + 3 * G::kSetIndex[2 * Set];
		}
	}

	/** 설정: C++ FObstacleConfig 기본값 = 거울 설정 obstacles 계수(몸·가림·먹이), 기본은 끔. 상수 = world.py OB_PASSES·OB_EPS·OB_SAMPLES. */
	inline FReport CheckConfig()
	{
		FReport R;
		const FObstacleConfig D;
		Detail::FCase C;
		C.Real(30, D.BodyR, G::kCfgBodyR);
		C.Int(31, D.bBlockSight ? 1 : 0, G::kCfgBlockSight);
		C.Int(32, D.bNoFood ? 1 : 0, G::kCfgNoFood);
		C.Int(33, (D.bEnabled || FWorldConfig().Obstacles.bEnabled || !FWorldConfig().Obstacles.Discs.empty()) ? 1 : 0, 0);
		C.Int(34, T3::kObstaclePasses, G::kPasses);
		C.Real(35, T3::kObstacleEps, G::kEps);
		C.Int(36, kObstacleFoodSamples, G::kSamples);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 미끄러짐: ObstacleSlide = obstacle_slide (새 q·부딪힘·물러남). */
	inline FReport CheckSlides()
	{
		FReport R;
		for (std::int32_t s = 0; s < G::kSlideCases; ++s)
		{
			std::int32_t K = 0;
			const double* D = Detail::SetDiscs(G::kSlideSet[s], K);
			const double* In = G::kSlideIn + 5 * s;
			double Qx = In[2];
			double Qy = In[3];
			const T3::FObstacleSlideResult Res = T3::ObstacleSlide(In[0], In[1], Qx, Qy, D, K, G::kCfgBodyR, In[4]);
			Detail::FCase C;
			C.Real(0, Qx, G::kSlideOut[2 * s]);
			C.Real(1, Qy, G::kSlideOut[2 * s + 1]);
			C.Int(2, Res.bHit ? 1 : 0, G::kSlideOutI[2 * s]);
			C.Int(3, Res.bBack ? 1 : 0, G::kSlideOutI[2 * s + 1]);
			R.Count0 += Res.bHit ? 1 : 0;
			R.Count1 += Res.bBack ? 1 : 0;
			Detail::Close(R, s, C);
		}
		return R;
	}

	/** 시선: SightBlocked = sight_blocked 한 쌍. */
	inline FReport CheckSights()
	{
		FReport R;
		for (std::int32_t s = 0; s < G::kSightCases; ++s)
		{
			std::int32_t K = 0;
			const double* D = Detail::SetDiscs(G::kSightSet[s], K);
			const double* In = G::kSightIn + 4 * s;
			const bool b = T3::SightBlocked(In[0], In[1], In[2], In[3], D, K);
			Detail::FCase C;
			C.Int(5, b ? 1 : 0, G::kSightOut[s]);
			R.Count0 += b ? 1 : 0;
			Detail::Close(R, s, C);
		}
		return R;
	}

	/** 먹이: FFoodGrid::ApplyObstacleFood = 처음 용량 × obstacle_food_factor (셀마다). */
	inline FReport CheckFood()
	{
		FReport R;
		const std::int32_t Cells = G::kFoodGw * G::kFoodGw;
		for (std::int32_t j = 0; j < G::kFoodLayouts; ++j)
		{
			std::int32_t K = 0;
			const double* D = Detail::SetDiscs(G::kFoodSet[j], K);
			FWorldConfig Cfg;
			Cfg.Obstacles.bEnabled = true;
			Cfg.Obstacles.Discs.assign(D, D + 3 * K);
			FFoodGrid F;
			F.Gw = G::kFoodGw;
			F.Cell = G::kFoodCell;
			F.Cap.assign(G::kFoodCap0 + Cells * j, G::kFoodCap0 + Cells * (j + 1));
			F.ApplyObstacleFood(Cfg);
			for (std::int32_t k = 0; k < Cells; ++k)
			{
				Detail::FCase C;
				C.Real(6, F.Cap[static_cast<size_t>(k)], G::kFoodCap1[Cells * j + k]);
				Detail::Close(R, Cells * j + k, C);
			}
		}
		return R;
	}

	/** 밀어내기: ObstaclePushOut = obstacle_push_out 한 개체 (늑대는 은신처 막기 원 밖 후보만). */
	inline FReport CheckPushes()
	{
		FReport R;
		for (std::int32_t s = 0; s < G::kPushCases; ++s)
		{
			const std::int32_t* I = G::kPushInt + 4 * s;
			const double* In = G::kPushIn + 4 * s;
			std::int32_t K = 0;
			const double* D = Detail::SetDiscs(I[0], K);
			FWorldConfig Cfg;
			Cfg.WorldSize = In[2];
			Cfg.Covers.clear();
			for (std::int32_t k = 0; k < I[3]; ++k)
			{
				const double* Cv = G::kPushCover + 3 * (I[2] + k);
				Cfg.Covers.push_back({Cv[0], Cv[1], Cv[2]});
			}
			Cfg.bShelterSafe = I[3] > 0;
			Cfg.ShelterWolfMargin = In[3];
			Cfg.Obstacles.bEnabled = true;
			Cfg.Obstacles.BodyR = G::kCfgBodyR;
			Cfg.Obstacles.Discs.assign(D, D + 3 * K);
			FVec2 P{In[0], In[1]};
			const std::int32_t Code = ObstaclePushOut(Cfg, P, I[1] != 0);
			Detail::FCase C;
			C.Real(7, P.X, G::kPushOut[2 * s]);
			C.Real(8, P.Y, G::kPushOut[2 * s + 1]);
			C.Int(9, Code, G::kPushOutI[s]);
			R.Count0 += Code == 1 ? 1 : 0;
			R.Count1 += Code == 2 ? 1 : 0;
			Detail::Close(R, s, C);
		}
		return R;
	}

	/** 한 스텝 장면의 위협 설정 (거울 세계: 제자리 식사 38·포만 450·은신처 안전과 진입 금지·무리 켬, 낮). */
	inline T3::FThreatConfig StepConfig()
	{
		T3::FThreatConfig Cfg;
		Cfg.PredEatCd = G::kStepEatCd;
		Cfg.bEatInPlace = true;
		Cfg.bWildSatiation = true;
		Cfg.SatSteps = G::kStepSatSteps;
		Cfg.bShelterSafe = true;
		Cfg.bShelterBlock = true;
		Cfg.Pack.bEnabled = true;
		return Cfg;
	}

	/**
	 * 한 스텝 장면: EcoWorldV3 C2 와 같은 순서 — 모든 늑대 PackPeek(원판 포함) → PackGoals → 늑대 순서로 Step (배회 선회 = 파이썬이 뽑은 값, 원판 = 그 세계 배치).
	 * 늑대 순번 짝수 = 잠행형, 홀수 = 추격형.
	 */
	inline FReport CheckSteps()
	{
		FReport R;
		const T3::FThreatConfig Cfg = StepConfig();
		const std::int32_t M = G::kStepWolves;
		const std::int32_t N = G::kStepPrey;
		const std::int32_t K = G::kStepCoverCount;
		std::vector<double> Discs;
		for (std::int32_t k = 0; k < K; ++k)
		{
			Discs.push_back(G::kStepCover[3 * k]);
			Discs.push_back(G::kStepCover[3 * k + 1]);
			Discs.push_back(G::kStepCover[3 * k + 2] + G::kStepWolfMargin);
		}
		std::vector<T3::FThreatSpec> Specs;
		for (std::int32_t m = 0; m < M; ++m)
		{
			Specs.push_back(m % 2 == 0 ? T3::MakeStalkerSpec(G::kStepPredSpeedMult, false, Cfg) : T3::MakeChaserSpec(G::kStepPredSpeedMult, false, false, Cfg));
		}
		std::vector<T3::FPreyView> Prey(static_cast<size_t>(N));
		std::vector<T3::FThreatState> States(static_cast<size_t>(M));
		std::vector<T3::FPackWolf> Wolves(static_cast<size_t>(M));
		std::vector<T3::FPackGoal> Goals(static_cast<size_t>(M));
		for (std::int32_t s = 0; s < G::kStepScenes; ++s)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kStepPreyIn + 5 * (s * N + i);
				T3::FPreyView& V = Prey[static_cast<size_t>(i)];
				V = T3::FPreyView();
				V.X = Pd[0];
				V.Y = Pd[1];
				V.MoveX = Pd[2];
				V.MoveY = Pd[3];
				V.bInCover = Pd[4] != 0.0;
				V.Behavior = T3::kPreyGraze;
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kStepWolfIn + 5 * (s * M + m);
				const std::int32_t* Wi = G::kStepWolfInI + 4 * (s * M + m);
				T3::FThreatState& T = States[static_cast<size_t>(m)];
				T = T3::FThreatState();
				T.PosX = Wd[0];
				T.PosY = Wd[1];
				T.HeadX = Wd[2];
				T.HeadY = Wd[3];
				T.Cooldown = Wi[0];
				T.SatLeft = Wi[1];
				T.StalkState = static_cast<T3::EStalkState>(Wi[2]);
				T.StalkLeft = Wi[3];
			}
			T3::FThreatStepInput Base;
			Base.Prey = Prey.data();
			Base.NumPrey = N;
			Base.Dark = 0.0;
			Base.WorldSize = G::kStepWorldSize;
			Base.Discs = Discs.data();
			Base.NumDiscs = K;
			Base.Obstacles = G::kStepDiscs;
			Base.NumObstacles = G::kStepDiscCount;
			Base.ObstacleBody = G::kCfgBodyR;
			Base.bObstacleSight = G::kStepSight != 0;
			for (std::int32_t m = 0; m < M; ++m)
			{
				Wolves[static_cast<size_t>(m)] = T3::PackPeek(Specs[static_cast<size_t>(m)], States[static_cast<size_t>(m)], Base, Cfg);
			}
			T3::PackGoals(Wolves.data(), M, Prey.data(), N, G::kStepCover, K, G::kStepWolfMargin, G::kStepWorldSize, Cfg.Pack, Goals.data());
			for (std::int32_t m = 0; m < M; ++m)
			{
				const T3::FPackGoal& Gm = Goals[static_cast<size_t>(m)];
				T3::FThreatStepInput In = Base;
				In.WanderTurn = G::kStepWolfIn[5 * (s * M + m) + 4];
				In.bPackHelp = Gm.bHelp;
				In.bPackWait = Gm.bWait;
				In.PackDirX = Gm.DirX;
				In.PackDirY = Gm.DirY;
				T3::FThreatState& T = States[static_cast<size_t>(m)];
				const T3::FThreatStepResult Res = T3::Step(Specs[static_cast<size_t>(m)], T, In, Cfg);
				const double* Od = G::kStepWolfOut + 4 * (s * M + m);
				const std::int32_t* Oi = G::kStepWolfOutI + 10 * (s * M + m);
				Detail::FCase C;
				C.Real(10, T.PosX, Od[0]);
				C.Real(11, T.PosY, Od[1]);
				C.Real(12, T.HeadX, Od[2]);
				C.Real(13, T.HeadY, Od[3]);
				C.Int(14, T.Cooldown, Oi[0]);
				C.Int(15, T.SatLeft, Oi[1]);
				C.Int(16, static_cast<std::int32_t>(T.StalkState), Oi[2]);
				C.Int(17, T.StalkLeft, Oi[3]);
				C.Int(18, Gm.bHelp ? 1 : 0, Oi[4]);
				C.Int(19, Res.Target, Oi[5]);
				C.Int(20, Res.Caught, Oi[6]);
				C.Int(21, Res.bObstacleHit ? 1 : 0, Oi[7]);
				C.Int(22, Res.bObstacleBack ? 1 : 0, Oi[8]);
				C.Int(23, Res.bObstacleDead ? 1 : 0, Oi[9]);
				R.Count0 += Res.bObstacleHit ? 1 : 0;
				R.Count1 += Res.bObstacleDead ? 1 : 0;
				R.Count2 += Res.Caught >= 0 ? 1 : 0;
				Detail::Close(R, s * M + m, C);
			}
		}
		return R;
	}

	/**
	 * 끄면 그대로: 원판을 넘기지 않은 Step 은 원판 칸을 읽지 않는다 — 같은 장면에서 원판 칸만 쓰레기 값(가림 켬·몸 반지름)으로 바꿔도
	 * Obstacles = nullptr 이면 결과가 비트 단위로 같다. 사례 = 장면·늑대.
	 */
	inline FReport CheckOffIgnores()
	{
		FReport R;
		const T3::FThreatConfig Cfg = StepConfig();
		const std::int32_t M = G::kStepWolves;
		const std::int32_t N = G::kStepPrey;
		std::vector<T3::FPreyView> Prey(static_cast<size_t>(N));
		for (std::int32_t s = 0; s < G::kStepScenes; s += 8)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kStepPreyIn + 5 * (s * N + i);
				Prey[static_cast<size_t>(i)] = T3::FPreyView();
				Prey[static_cast<size_t>(i)].X = Pd[0];
				Prey[static_cast<size_t>(i)].Y = Pd[1];
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kStepWolfIn + 5 * (s * M + m);
				const T3::FThreatSpec Spec = m % 2 == 0 ? T3::MakeStalkerSpec(G::kStepPredSpeedMult, false, Cfg) : T3::MakeChaserSpec(G::kStepPredSpeedMult, false, false, Cfg);
				T3::FThreatState A, B;
				A.PosX = B.PosX = Wd[0];
				A.PosY = B.PosY = Wd[1];
				A.HeadX = B.HeadX = Wd[2];
				A.HeadY = B.HeadY = Wd[3];
				T3::FThreatStepInput Ia;
				Ia.Prey = Prey.data();
				Ia.NumPrey = N;
				Ia.WorldSize = G::kStepWorldSize;
				Ia.WanderTurn = Wd[4];
				T3::FThreatStepInput Ib = Ia;
				Ib.bObstacleSight = true;
				Ib.ObstacleBody = 3.0;
				Ib.NumObstacles = 0;
				const T3::FThreatStepResult Ra = T3::Step(Spec, A, Ia, Cfg);
				const T3::FThreatStepResult Rb = T3::Step(Spec, B, Ib, Cfg);
				Detail::FCase C;
				C.Real(10, A.PosX, B.PosX);
				C.Real(11, A.PosY, B.PosY);
				C.Real(12, A.HeadX, B.HeadX);
				C.Real(13, A.HeadY, B.HeadY);
				C.Int(19, Ra.Target, Rb.Target);
				C.Int(21, (Ra.bObstacleHit || Rb.bObstacleHit) ? 1 : 0, 0);
				Detail::Close(R, s * M + m, C);
			}
		}
		return R;
	}
}
