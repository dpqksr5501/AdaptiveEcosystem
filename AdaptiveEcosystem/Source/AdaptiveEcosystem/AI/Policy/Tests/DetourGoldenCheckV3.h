// v3 야생 2단계 3 의 6) 장애물 돌아가기 골든 대조 — EcoThreatModel.h (FDetourConfig·DetourCandidate·DetourStep·Step 7′·8″·PackPeek)·
// EcoWorldV3.h (FObstacleConfig::Detour)를 DetourGoldenVectorsV3.h (herbivore_rl/export_golden_v3_detour.py, 세계 configs/v3_wild2_obstacle_mirror.yaml)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<vector>` 와 엔진 무관 v3 세계 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoObstacleV3Test.cpp (AdaptiveEcosystem.Policy.V3.Obstacle.DetourGolden)
//   g++ 하네스       herbivore_rl/tests/cpp/detour_v3_main.cpp (herbivore_rl/tests/test_wild2_detour.py)
// 모든 칸이 비트 단위로 같아야 한다(실수도 == — 파이썬과 같은 순서로 계산한다).
//
// 칸 번호 (FReport::FirstField):
//   설정   0 막힘 몫, 1 빈 몫, 2 앞 보기, 3 최대 스텝, 4 돕기 그만둠 스텝, 5 돕지 않는 스텝, 6 기본 끔, 7 돌리기 표, 8 후보·차례 표, 9 몸 반지름
//   한 번  10 vx, 11 vy, 12 방향 x, 13 방향 y, 14 left, 15 side, 16 steps, 17 썼나, 18 시작, 19 못 찾음
//   궤적   20 x, 21 y, 22 left, 23 side, 24 steps, 25 썼나
//   스텝   30 위치 x, 31 위치 y, 32 heading x, 33 heading y, 34 돕기, 35 돌아섬, 36 left, 37 side, 38 steps, 39 돕지 않는 남은 스텝, 40 썼나, 41 그만둠,
//          42 느린 스텝

#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

#include "../EcoWorldV3.h"
#include "../DetourGoldenVectorsV3.h"

namespace EcoWorldV3::DetourCheck
{
	namespace G = EcoWorldV3::GoldenDetour;
	namespace T3 = EcoThreatV3;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int32_t Count0 = 0;       // 묶음마다 C++ 이 낸 수 (골든 합과 견준다): 한 번·궤적·스텝 썼나
		std::int32_t Count1 = 0;       // 한 번 시작·스텝 그만둠
		std::int32_t Count2 = 0;       // 한 번 못 찾음·스텝 돌아섬

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

		/** 거울 설정의 돌아가기 계수 (켬). */
		inline T3::FDetourConfig MirrorDetour()
		{
			T3::FDetourConfig D;
			D.bEnabled = true;
			D.BlockFrac = G::kCfgBlock;
			D.FreeFrac = G::kCfgFree;
			D.Probe = G::kCfgProbe;
			D.MaxSteps = G::kCfgSteps;
			D.HelpBlock = G::kCfgHelpBlock;
			D.HelpDrop = G::kCfgHelpDrop;
			return D;
		}
	}

	/** 설정: C++ FDetourConfig 기본값 = 거울 설정 obstacles.detour_* (켬 칸만 기본 끔), 돌리기·후보·차례 표 = world.py DETOUR_*. */
	inline FReport CheckConfig()
	{
		FReport R;
		const T3::FDetourConfig D;
		Detail::FCase C;
		C.Real(0, D.BlockFrac, G::kCfgBlock);
		C.Real(1, D.FreeFrac, G::kCfgFree);
		C.Real(2, D.Probe, G::kCfgProbe);
		C.Int(3, D.MaxSteps, G::kCfgSteps);
		C.Int(4, D.HelpBlock, G::kCfgHelpBlock);
		C.Int(5, D.HelpDrop, G::kCfgHelpDrop);
		C.Int(6, (D.bEnabled || FObstacleConfig().Detour.bEnabled || FWorldConfig().Obstacles.Detour.bEnabled) ? 1 : 0, 0);
		for (std::int32_t k = 0; k <= T3::kDetourHalf; ++k)
		{
			C.Real(7, T3::kDetourRot[k][0], G::kRot[2 * k]);
			C.Real(7, T3::kDetourRot[k][1], G::kRot[2 * k + 1]);
		}
		C.Int(8, T3::kDetourHalf, G::kHalf);
		for (std::int32_t j = 0; j < T3::kDetourCands; ++j)
		{
			C.Int(8, T3::kDetourCandK[j], G::kCandK[j]);
			C.Int(8, T3::kDetourCandSg[j], G::kCandSg[j]);
			C.Int(8, T3::kDetourOrderFresh[j], G::kOrderFresh[j]);
			C.Int(8, T3::kDetourOrderPos[j], G::kOrderPos[j]);
			C.Int(8, T3::kDetourOrderNeg[j], G::kOrderNeg[j]);
		}
		C.Real(9, FObstacleConfig().BodyR, G::kCfgBodyR);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 한 번: DetourStep = detour_moves 한 개체 (새 v·고른 방향·상태·썼나·시작·못 찾음). */
	inline FReport CheckOnes()
	{
		FReport R;
		const T3::FDetourConfig Cfg = Detail::MirrorDetour();
		for (std::int32_t s = 0; s < G::kOneCases; ++s)
		{
			const std::int32_t* I = G::kOneInt + 6 * s;
			const double* In = G::kOneIn + 5 * s;
			std::int32_t K = 0;
			const double* D = Detail::SetDiscs(I[0], K);
			const double* Walls = nullptr;
			std::int32_t NumWalls = 0;
			if (I[1] >= 0)
			{
				Walls = G::kWallDiscs + 3 * G::kWallIndex[2 * I[1]];
				NumWalls = G::kWallIndex[2 * I[1] + 1];
			}
			T3::FDetourState St;
			St.Left = I[3];
			St.Side = I[4];
			St.Steps = I[5];
			double Vx = In[2];
			double Vy = In[3];
			const T3::FDetourResult Res = T3::DetourStep(In[0], In[1], Vx, Vy, St, D, K, G::kCfgBodyR, In[4], I[2] != 0, Walls, NumWalls, Cfg);
			const double* O = G::kOneOut + 4 * s;
			const std::int32_t* Oi = G::kOneOutI + 6 * s;
			Detail::FCase C;
			C.Real(10, Vx, O[0]);
			C.Real(11, Vy, O[1]);
			C.Real(12, Res.bUsed ? Res.DirX : 0.0, O[2]);
			C.Real(13, Res.bUsed ? Res.DirY : 0.0, O[3]);
			C.Int(14, St.Left, Oi[0]);
			C.Int(15, St.Side, Oi[1]);
			C.Int(16, St.Steps, Oi[2]);
			C.Int(17, Res.bUsed ? 1 : 0, Oi[3]);
			C.Int(18, Res.bStart ? 1 : 0, Oi[4]);
			C.Int(19, Res.bFail ? 1 : 0, Oi[5]);
			R.Count0 += Res.bUsed ? 1 : 0;
			R.Count1 += Res.bStart ? 1 : 0;
			R.Count2 += Res.bFail ? 1 : 0;
			Detail::Close(R, s, C);
		}
		return R;
	}

	/** 궤적: 스텝마다 목표 쪽 V → DetourStep → 이동(사슴 clip + ObstacleSlide(Size), 위협 ObstacleSlide(−1)). 사례 = 줄. */
	inline FReport CheckPaths()
	{
		FReport R;
		const T3::FDetourConfig Cfg = Detail::MirrorDetour();
		for (std::int32_t s = 0; s < G::kPathCases; ++s)
		{
			const std::int32_t* I = G::kPathInt + 4 * s;
			const double* In = G::kPathIn + 6 * s;
			std::int32_t K = 0;
			const double* D = Detail::SetDiscs(I[0], K);
			const bool bDeer = I[1] != 0;
			const double Size = In[5];
			double Px = In[0];
			double Py = In[1];
			T3::FDetourState St;
			for (std::int32_t t = 0; t < I[2]; ++t)
			{
				const double Tx = In[2] - Px;
				const double Ty = In[3] - Py;
				const double Nn = std::sqrt(Tx * Tx + Ty * Ty);
				double Vx = Nn > In[4] ? Tx / Nn * In[4] : 0.0;
				double Vy = Nn > In[4] ? Ty / Nn * In[4] : 0.0;
				const T3::FDetourResult Res = T3::DetourStep(Px, Py, Vx, Vy, St, D, K, G::kCfgBodyR, Size, bDeer, nullptr, 0, Cfg);
				double Qx = 0.0;
				double Qy = 0.0;
				T3::DetourMoveTest(Px, Py, Vx, Vy, D, K, G::kCfgBodyR, Size, bDeer, Qx, Qy);
				Px = Qx;
				Py = Qy;
				const std::int32_t Row = I[3] + t;
				Detail::FCase C;
				C.Real(20, Px, G::kPathOut[2 * Row]);
				C.Real(21, Py, G::kPathOut[2 * Row + 1]);
				C.Int(22, St.Left, G::kPathOutI[4 * Row]);
				C.Int(23, St.Side, G::kPathOutI[4 * Row + 1]);
				C.Int(24, St.Steps, G::kPathOutI[4 * Row + 2]);
				C.Int(25, Res.bUsed ? 1 : 0, G::kPathOutI[4 * Row + 3]);
				R.Count0 += Res.bUsed ? 1 : 0;
				Detail::Close(R, Row, C);
			}
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
	 * 한 스텝 장면: EcoWorldV3 C2 와 같은 순서 — 모든 늑대 PackPeek(원판 포함, 돌아가기 없음) → PackGoals → 늑대 순서로 Step (In.Detour = 거울 계수).
	 * 늑대 순번 짝수 = 잠행형, 홀수 = 추격형.
	 */
	inline FReport CheckSteps()
	{
		FReport R;
		const T3::FThreatConfig Cfg = StepConfig();
		const T3::FDetourConfig Det = Detail::MirrorDetour();
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
				const std::int32_t* Wi = G::kStepWolfInI + 9 * (s * M + m);
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
				T.Detour.Left = Wi[4];
				T.Detour.Side = Wi[5];
				T.Detour.Steps = Wi[6];
				T.PackDrop = Wi[7];
				T.DetourSlow = Wi[8];
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
				In.Detour = &Det;
				T3::FThreatState& T = States[static_cast<size_t>(m)];
				const T3::FThreatStepResult Res = T3::Step(Specs[static_cast<size_t>(m)], T, In, Cfg);
				const double* Od = G::kStepWolfOut + 4 * (s * M + m);
				const std::int32_t* Oi = G::kStepWolfOutI + 9 * (s * M + m);
				Detail::FCase C;
				C.Real(30, T.PosX, Od[0]);
				C.Real(31, T.PosY, Od[1]);
				C.Real(32, T.HeadX, Od[2]);
				C.Real(33, T.HeadY, Od[3]);
				C.Int(34, Gm.bHelp ? 1 : 0, Oi[0]);
				C.Int(35, Res.bObstacleDead ? 1 : 0, Oi[1]);
				C.Int(36, T.Detour.Left, Oi[2]);
				C.Int(37, T.Detour.Side, Oi[3]);
				C.Int(38, T.Detour.Steps, Oi[4]);
				C.Int(39, T.PackDrop, Oi[5]);
				C.Int(40, Res.bDetour ? 1 : 0, Oi[6]);
				C.Int(41, Res.bPackDrop ? 1 : 0, Oi[7]);
				C.Int(42, T.DetourSlow, Oi[8]);
				R.Count0 += Res.bDetour ? 1 : 0;
				R.Count1 += Res.bPackDrop ? 1 : 0;
				R.Count2 += Res.bObstacleDead ? 1 : 0;
				Detail::Close(R, s * M + m, C);
			}
		}
		return R;
	}

	/**
	 * 끄면 그대로: In.Detour = nullptr 이거나 꺼진 계수면 Step 이 돌아가기 칸을 읽지 않는다 — 같은 장면에서 상태 칸에 쓰레기 값(Left·Side·Steps)을 넣고 꺼진
	 * 계수를 넘겨도, 넘기지 않은 Step 과 위치·heading 이 비트 단위로 같다. 사례 = 장면·늑대.
	 */
	inline FReport CheckOffIgnores()
	{
		FReport R;
		const T3::FThreatConfig Cfg = StepConfig();
		T3::FDetourConfig Off = Detail::MirrorDetour();
		Off.bEnabled = false;
		const std::int32_t M = G::kStepWolves;
		const std::int32_t N = G::kStepPrey;
		std::vector<T3::FPreyView> Prey(static_cast<size_t>(N));
		for (std::int32_t s = 0; s < G::kStepScenes; s += 4)
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
				B.Detour.Left = 7;
				B.Detour.Side = -1;
				B.Detour.Steps = 3;
				T3::FThreatStepInput Ia;
				Ia.Prey = Prey.data();
				Ia.NumPrey = N;
				Ia.WorldSize = G::kStepWorldSize;
				Ia.WanderTurn = Wd[4];
				Ia.Obstacles = G::kStepDiscs;
				Ia.NumObstacles = G::kStepDiscCount;
				Ia.ObstacleBody = G::kCfgBodyR;
				T3::FThreatStepInput Ib = Ia;
				Ib.Detour = &Off;
				const T3::FThreatStepResult Ra = T3::Step(Spec, A, Ia, Cfg);
				const T3::FThreatStepResult Rb = T3::Step(Spec, B, Ib, Cfg);
				Detail::FCase C;
				C.Real(30, A.PosX, B.PosX);
				C.Real(31, A.PosY, B.PosY);
				C.Real(32, A.HeadX, B.HeadX);
				C.Real(33, A.HeadY, B.HeadY);
				C.Int(36, B.Detour.Left, 7);
				C.Int(40, (Ra.bDetour || Rb.bDetour) ? 1 : 0, 0);
				Detail::Close(R, s * M + m, C);
			}
		}
		return R;
	}
}
