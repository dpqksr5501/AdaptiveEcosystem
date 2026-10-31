// v3 야생 2단계 2 늑대 무리 협동 골든 대조 — EcoThreatModel.h (FPackHuntConfig·PackPeek·PackGoals·Step 6b′)를
// PackGoldenVectorsV3.h (herbivore_rl/export_golden_v3_pack.py, 세계 configs/v3_wild2_pack_mirror.yaml)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<vector>` 와 엔진 무관 위협 모델 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoPackV3Test.cpp (AdaptiveEcosystem.Policy.V3.Pack.*)
//   g++ 하네스       herbivore_rl/tests/cpp/pack_v3_main.cpp (herbivore_rl/tests/test_wild2_pack.py)
// 모든 칸이 비트 단위로 같아야 한다(실수도 == — 파이썬 pack_goals·_step_predators_v3 와 같은 순서로 계산한다).
//
// 칸 번호 (FReport::FirstField):
//   목표   0 돕기, 1 기다림, 2 문, 3 고른 사슴, 4 방향 x, 5 방향 y
//   스텝   10 위치 x, 11 위치 y, 12 heading x, 13 heading y, 14 쿨다운, 15 배부름, 16 잠행 상태, 17 남은 수, 18 돕기, 19 기다림, 20 문,
//          21 고른 사슴, 22 표적, 23 잡은 사슴
//   설정   30 + 계수 번호 (join_r, lead, door_r, door_cos, wait_r)

#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

#include "../EcoThreatModel.h"
#include "../PackGoldenVectorsV3.h"

namespace EcoThreatV3::PackCheck
{
	namespace G = EcoThreatV3::GoldenPack;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례 (목표 = 늑대, 스텝 = 늑대)
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int32_t Help = 0;         // C++ 이 낸 돕기·기다림·문·포획 수 (골든 합과 견준다)
		std::int32_t Wait = 0;
		std::int32_t Door = 0;
		std::int32_t Catches = 0;

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
	}

	/** 설정: C++ FPackHuntConfig 기본값 = 거울 설정 wild_pack 계수, 기본은 끔. */
	inline FReport CheckConfig()
	{
		FReport R;
		const FPackHuntConfig D;
		Detail::FCase C;
		C.Int(29, D.bEnabled ? 1 : 0, 0);
		C.Int(29, FThreatConfig().Pack.bEnabled ? 1 : 0, 0);
		C.Real(30, D.JoinR, G::kCfg_join_r);
		C.Real(31, D.Lead, G::kCfg_lead);
		C.Real(32, D.DoorR, G::kCfg_door_r);
		C.Real(33, D.DoorCos, G::kCfg_door_cos);
		C.Real(34, D.WaitR, G::kCfg_wait_r);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 목표 장면: PackGoals = 파이썬 pack_goals (늑대마다 돕기·기다림·문·고른 사슴·방향). */
	inline FReport CheckGoals()
	{
		FReport R;
		std::vector<FPackWolf> Wolves;
		std::vector<FPreyView> Prey;
		std::vector<FPackGoal> Out;
		for (std::int32_t s = 0; s < G::kGoalScenes; ++s)
		{
			const std::int32_t* I = G::kGoalInt + 6 * s;
			const double* D = G::kGoalDbl + 7 * s;
			const std::int32_t M = I[0], N = I[1], K = I[2], WolfStart = I[3], PreyStart = I[4], CoverStart = I[5];
			FPackHuntConfig Cfg;
			Cfg.bEnabled = true;
			Cfg.JoinR = D[2];
			Cfg.Lead = D[3];
			Cfg.DoorR = D[4];
			Cfg.DoorCos = D[5];
			Cfg.WaitR = D[6];
			Wolves.assign(static_cast<size_t>(M), FPackWolf());
			Prey.assign(static_cast<size_t>(N), FPreyView());
			Out.assign(static_cast<size_t>(M), FPackGoal());
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kGoalWolfD + 4 * (WolfStart + m);
				const std::int32_t* Wi = G::kGoalWolfI + 3 * (WolfStart + m);
				FPackWolf& P = Wolves[static_cast<size_t>(m)];
				P.X = Wd[0];
				P.Y = Wd[1];
				P.HeadX = Wd[2];
				P.HeadY = Wd[3];
				P.bLeader = Wi[0] != 0;
				P.bHelper = Wi[1] != 0;
				P.Target = Wi[2];
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kGoalPrey + 4 * (PreyStart + i);
				FPreyView& V = Prey[static_cast<size_t>(i)];
				V.X = Pd[0];
				V.Y = Pd[1];
				V.MoveX = Pd[2];
				V.MoveY = Pd[3];
			}
			PackGoals(Wolves.data(), M, Prey.data(), N, K > 0 ? G::kGoalCover + 3 * CoverStart : nullptr, K, D[1], D[0], Cfg, Out.data());
			for (std::int32_t m = 0; m < M; ++m)
			{
				const std::int32_t* Oi = G::kGoalOutI + 4 * (WolfStart + m);
				const double* Od = G::kGoalOutD + 2 * (WolfStart + m);
				const FPackGoal& Gm = Out[static_cast<size_t>(m)];
				Detail::FCase C;
				C.Int(0, Gm.bHelp ? 1 : 0, Oi[0]);
				C.Int(1, Gm.bWait ? 1 : 0, Oi[1]);
				C.Int(2, Gm.bDoor ? 1 : 0, Oi[2]);
				C.Int(3, Gm.Prey, Oi[3]);
				C.Real(4, Gm.DirX, Od[0]);
				C.Real(5, Gm.DirY, Od[1]);
				R.Help += Gm.bHelp ? 1 : 0;
				R.Wait += Gm.bWait ? 1 : 0;
				R.Door += Gm.bDoor ? 1 : 0;
				Detail::Close(R, WolfStart + m, C);
			}
		}
		return R;
	}

	/** 한 스텝 장면의 위협 설정 (거울 세계: 제자리 식사 38·포만 450·은신처 안전과 진입 금지·무리 켬, 낮). */
	inline FThreatConfig StepConfig()
	{
		FThreatConfig Cfg;
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
	 * 한 스텝 장면: EcoWorldV3 C2 와 같은 순서 — 모든 늑대 PackPeek → PackGoals → 늑대 순서로 Step (배회 선회 = 파이썬이 뽑은 값).
	 * 늑대 순번 짝수 = 잠행형, 홀수 = 추격형 (거울 세계 integrated_stage.wolf_kinds 'alternate' = C++ WolfSpecForOrdinal).
	 */
	inline FReport CheckSteps()
	{
		FReport R;
		const FThreatConfig Cfg = StepConfig();
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
		std::vector<FThreatSpec> Specs;
		for (std::int32_t m = 0; m < M; ++m)
		{
			Specs.push_back(m % 2 == 0 ? MakeStalkerSpec(G::kStepPredSpeedMult, false, Cfg) : MakeChaserSpec(G::kStepPredSpeedMult, false, false, Cfg));
		}
		std::vector<FPreyView> Prey(static_cast<size_t>(N));
		std::vector<FThreatState> States(static_cast<size_t>(M));
		std::vector<FPackWolf> Wolves(static_cast<size_t>(M));
		std::vector<FPackGoal> Goals(static_cast<size_t>(M));
		for (std::int32_t s = 0; s < G::kStepScenes; ++s)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kStepPreyIn + 5 * (s * N + i);
				FPreyView& V = Prey[static_cast<size_t>(i)];
				V = FPreyView();
				V.X = Pd[0];
				V.Y = Pd[1];
				V.MoveX = Pd[2];
				V.MoveY = Pd[3];
				V.bInCover = Pd[4] != 0.0;
				V.Behavior = kPreyGraze;
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kStepWolfIn + 5 * (s * M + m);
				const std::int32_t* Wi = G::kStepWolfInI + 4 * (s * M + m);
				FThreatState& T = States[static_cast<size_t>(m)];
				T = FThreatState();
				T.PosX = Wd[0];
				T.PosY = Wd[1];
				T.HeadX = Wd[2];
				T.HeadY = Wd[3];
				T.Cooldown = Wi[0];
				T.SatLeft = Wi[1];
				T.StalkState = static_cast<EStalkState>(Wi[2]);
				T.StalkLeft = Wi[3];
			}
			FThreatStepInput Base;
			Base.Prey = Prey.data();
			Base.NumPrey = N;
			Base.Dark = 0.0;
			Base.WorldSize = G::kStepWorldSize;
			Base.Discs = Discs.data();
			Base.NumDiscs = K;
			for (std::int32_t m = 0; m < M; ++m)
			{
				Wolves[static_cast<size_t>(m)] = PackPeek(Specs[static_cast<size_t>(m)], States[static_cast<size_t>(m)], Base, Cfg);
			}
			PackGoals(Wolves.data(), M, Prey.data(), N, G::kStepCover, K, G::kStepWolfMargin, G::kStepWorldSize, Cfg.Pack, Goals.data());
			for (std::int32_t m = 0; m < M; ++m)
			{
				const FPackGoal& Gm = Goals[static_cast<size_t>(m)];
				FThreatStepInput In = Base;
				In.WanderTurn = G::kStepWolfIn[5 * (s * M + m) + 4];
				In.bPackHelp = Gm.bHelp;
				In.bPackWait = Gm.bWait;
				In.PackDirX = Gm.DirX;
				In.PackDirY = Gm.DirY;
				FThreatState& T = States[static_cast<size_t>(m)];
				const FThreatStepResult Res = Step(Specs[static_cast<size_t>(m)], T, In, Cfg);
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
				C.Int(19, Gm.bWait ? 1 : 0, Oi[5]);
				C.Int(20, Gm.bDoor ? 1 : 0, Oi[6]);
				C.Int(21, Gm.Prey, Oi[7]);
				C.Int(22, Res.Target, Oi[8]);
				C.Int(23, Res.Caught, Oi[9]);
				R.Help += Gm.bHelp ? 1 : 0;
				R.Wait += Gm.bWait ? 1 : 0;
				R.Door += Gm.bDoor ? 1 : 0;
				R.Catches += Res.Caught >= 0 ? 1 : 0;
				Detail::Close(R, s * M + m, C);
			}
		}
		return R;
	}

	/**
	 * 끄면 그대로: 무리를 끈 설정의 PackGoals 는 아무도 바꾸지 않고, In 무리 칸이 기본값인 Step 은 지금과 같다 (돕는 늑대 자리에 다른 방향을 넣어도
	 * bPackHelp 가 거짓이면 결과가 같다). 한 스텝 장면 모두로 본다.
	 */
	inline FReport CheckOffIgnores()
	{
		FReport R;
		FThreatConfig Cfg = StepConfig();
		Cfg.Pack.bEnabled = false;
		const std::int32_t M = G::kStepWolves;
		const std::int32_t N = G::kStepPrey;
		std::vector<FPreyView> Prey(static_cast<size_t>(N));
		std::vector<FPackWolf> Wolves(static_cast<size_t>(M));
		std::vector<FPackGoal> Goals(static_cast<size_t>(M));
		std::vector<double> Discs;
		for (std::int32_t k = 0; k < G::kStepCoverCount; ++k)
		{
			Discs.push_back(G::kStepCover[3 * k]);
			Discs.push_back(G::kStepCover[3 * k + 1]);
			Discs.push_back(G::kStepCover[3 * k + 2] + G::kStepWolfMargin);
		}
		for (std::int32_t s = 0; s < G::kStepScenes; ++s)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kStepPreyIn + 5 * (s * N + i);
				FPreyView& V = Prey[static_cast<size_t>(i)];
				V = FPreyView();
				V.X = Pd[0];
				V.Y = Pd[1];
				V.MoveX = Pd[2];
				V.MoveY = Pd[3];
				V.bInCover = Pd[4] != 0.0;
			}
			FThreatStepInput Base;
			Base.Prey = Prey.data();
			Base.NumPrey = N;
			Base.WorldSize = G::kStepWorldSize;
			Base.Discs = Discs.data();
			Base.NumDiscs = G::kStepCoverCount;
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kStepWolfIn + 5 * (s * M + m);
				const std::int32_t* Wi = G::kStepWolfInI + 4 * (s * M + m);
				FThreatState T;
				T.PosX = Wd[0];
				T.PosY = Wd[1];
				T.HeadX = Wd[2];
				T.HeadY = Wd[3];
				T.Cooldown = Wi[0];
				T.SatLeft = Wi[1];
				T.StalkState = static_cast<EStalkState>(Wi[2]);
				T.StalkLeft = Wi[3];
				const FThreatSpec Spec = m % 2 == 0 ? MakeStalkerSpec(G::kStepPredSpeedMult, false, Cfg) : MakeChaserSpec(G::kStepPredSpeedMult, false, false, Cfg);
				Wolves[static_cast<size_t>(m)] = PackPeek(Spec, T, Base, Cfg);
				FThreatState A = T;
				FThreatState B = T;
				FThreatStepInput Ia = Base;
				Ia.WanderTurn = Wd[4];
				FThreatStepInput Ib = Ia;
				Ib.PackDirX = 0.6;    // bPackHelp 거짓이면 읽지 않는다
				Ib.PackDirY = -0.8;
				Ib.bPackWait = true;
				const FThreatStepResult Ra = Step(Spec, A, Ia, Cfg);
				const FThreatStepResult Rb = Step(Spec, B, Ib, Cfg);
				Detail::FCase C;
				C.Real(10, B.PosX, A.PosX);
				C.Real(11, B.PosY, A.PosY);
				C.Real(12, B.HeadX, A.HeadX);
				C.Real(13, B.HeadY, A.HeadY);
				C.Int(22, Rb.Target, Ra.Target);
				C.Int(23, Rb.Caught, Ra.Caught);
				Detail::Close(R, s * M + m, C);
			}
			PackGoals(Wolves.data(), M, Prey.data(), N, G::kStepCover, G::kStepCoverCount, G::kStepWolfMargin, G::kStepWorldSize, Cfg.Pack,
					  Goals.data());
			for (std::int32_t m = 0; m < M; ++m)
			{
				Detail::FCase C;
				C.Int(18, Goals[static_cast<size_t>(m)].bHelp ? 1 : 0, 0);
				Detail::Close(R, s * M + m, C);
			}
		}
		return R;
	}
}
