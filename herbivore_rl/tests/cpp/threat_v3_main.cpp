// v3 위협 모델 파리티 하네스 — 언리얼 없이 C++ 위협 스텝(EcoThreatV3::Step)이 파이썬 학습 세계(world.py)와 같은 값을 내는지 본다.
//
//   g++ 로 컴파일해서 실행하면 묶음별 최대 실수 오차와 불일치 수를 stdout 에 찍고, 하나라도 어긋나면 종료 코드 1.
//   검사 내용은 UE 자동화 시험(AI/Policy/Tests/EcoThreatModelV3Test.cpp)과 같다.
//
// 이 파일이 include 하는 것:
//   EcoThreatModel.h          실제 언리얼 모듈의 위협 모델 (엔진 의존 없음)
//   ThreatGoldenVectorsV3.h   export_golden_v3_threat.py 생성
//
// 자동 실행: herbivore_rl/tests/test_threat_golden_v3.py

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>

#include "EcoThreatModel.h"
#include "ThreatGoldenVectorsV3.h"

using namespace EcoThreatV3;
using namespace EcoThreatV3::Golden;

namespace
{
	struct FCase
	{
		FThreatSpec Spec;
		FThreatState State;
		std::vector<FPreyView> Prey;
		std::vector<double> Roll;
		FThreatStepInput In;
	};

	FThreatSpec SpecOf(int n)
	{
		FThreatSpec S;
		S.Type = static_cast<EThreatType>(kSpecType[n]);
		S.bRanged = kSpecRanged[n] != 0;
		S.bNocturnal = kSpecNocturnal[n] != 0;
		S.BaseSpeed = kSpecBaseSpeed[n];
		S.CatchRadius = kSpecCatchR[n];
		return S;
	}

	FThreatState PreStateOf(int n)
	{
		FThreatState T;
		T.PosX = kPrePos[n * 2];
		T.PosY = kPrePos[n * 2 + 1];
		T.HeadX = kPreHead[n * 2];
		T.HeadY = kPreHead[n * 2 + 1];
		T.Cooldown = kPreInt[n * 5];
		T.StalkState = static_cast<EStalkState>(kPreInt[n * 5 + 1]);
		T.StalkLeft = kPreInt[n * 5 + 2];
		T.PlayerMode = static_cast<EPlayerMode>(kPreInt[n * 5 + 3]);
		T.PlayerLeft = kPreInt[n * 5 + 4];
		return T;
	}

	// 사례 n 의 입력 (State 는 PreStateOf). Prey·Roll 을 채우고 In 이 그것을 가리킨다
	void Build(int n, FCase& C)
	{
		C.Spec = SpecOf(n);
		C.State = PreStateOf(n);
		C.Prey.clear();
		C.Roll.clear();
		for (int k = 0; k < kPreyCount[n]; ++k)
		{
			const int p = kPreyBegin[n] + k;
			FPreyView P;
			P.X = kPreyPos[p * 2];
			P.Y = kPreyPos[p * 2 + 1];
			P.Behavior = kPreyBehavior[p];
			P.bHideArrived = kPreyHideArrived[p] != 0;
			P.bInCover = kPreyInCover[p] != 0;
			P.bAlive = true;
			C.Prey.push_back(P);
			C.Roll.push_back(kPreyRoll[p]);
		}
		C.In = FThreatStepInput();
		C.In.Prey = C.Prey.empty() ? nullptr : C.Prey.data();
		C.In.NumPrey = static_cast<std::int32_t>(C.Prey.size());
		C.In.RangedRoll = C.Spec.bRanged ? C.Roll.data() : nullptr;
		C.In.Dark = kDark[n];
		C.In.WorldSize = kWorldSize[n];
		C.In.WanderTurn = kTurn[n];
		C.In.PlayerModeU0 = kModeU[n * 2];
		C.In.PlayerModeU1 = kModeU[n * 2 + 1];
	}

	double Upd(double& MaxErr, double A, double B)
	{
		const double E = std::fabs(A - B);
		MaxErr = E > MaxErr ? E : MaxErr;
		return E;
	}

	// 사례 n 의 기대와 비교. Shift = 결과 색인에 더할 값 (죽은 초식을 앞에 끼운 시험). 어긋나면 이유를 Why 에 적고 false
	bool Compare(int n, const FThreatState& T, const FThreatStepResult& R, double& MaxErr, int Shift, char* Why, int WhyLen)
	{
		const double Tol = kFloatTolerance;
		bool bOk = true;
		Why[0] = 0;
		auto Fail = [&](const char* What) {
			if (bOk)
			{
				std::snprintf(Why, WhyLen, "%s", What);
			}
			bOk = false;
		};
		if (Upd(MaxErr, T.PosX, kPostPos[n * 2]) > Tol || Upd(MaxErr, T.PosY, kPostPos[n * 2 + 1]) > Tol)
		{
			Fail("pos");
		}
		if (Upd(MaxErr, T.HeadX, kPostHead[n * 2]) > Tol || Upd(MaxErr, T.HeadY, kPostHead[n * 2 + 1]) > Tol)
		{
			Fail("head");
		}
		if (Upd(MaxErr, T.VelX, kPostVel[n * 2]) > Tol || Upd(MaxErr, T.VelY, kPostVel[n * 2 + 1]) > Tol)
		{
			Fail("vel");
		}
		if (Upd(MaxErr, R.Speed, kOutSpeed[n]) > Tol)
		{
			Fail("speed");
		}
		if (Upd(MaxErr, R.TargetPerceived, kOutTargetPerceived[n]) > Tol)
		{
			Fail("target_perceived");
		}
		const int Ints[5] = {T.Cooldown, static_cast<int>(T.StalkState), T.StalkLeft, static_cast<int>(T.PlayerMode),
							 T.PlayerLeft};
		static const char* IntNames[5] = {"cooldown", "stalk_state", "stalk_left", "player_mode", "player_left"};
		for (int k = 0; k < 5; ++k)
		{
			if (Ints[k] != kPostInt[n * 5 + k])
			{
				Fail(IntNames[k]);
			}
		}
		const std::uint8_t Bits = static_cast<std::uint8_t>((R.bAsleep ? kOutAsleep : 0) | (R.bHunting ? kOutHunting : 0) |
															(R.bHasTarget ? kOutHasTarget : 0) | (R.bWallHit ? kOutWall : 0) |
															(R.bPounceStart ? kOutPounceStart : 0) |
															(R.bChargeStart ? kOutChargeStart : 0) |
															(R.bNewPlayerMode ? kOutNewMode : 0));
		if (Bits != kOutBits[n])
		{
			Fail("out_bits");
		}
		const int WantTarget = kOutTarget[n] >= 0 ? kOutTarget[n] + Shift : -1;
		const int WantCaught = kOutCaught[n] >= 0 ? kOutCaught[n] + Shift : -1;
		if (R.Target != WantTarget || T.Target != WantTarget)
		{
			Fail("target");
		}
		if (R.Caught != WantCaught)
		{
			Fail("caught");
		}
		if (T.bAsleep != R.bAsleep)
		{
			Fail("hook_asleep");
		}
		return bOk;
	}

	// 상태 칸을 하나씩 비교 (구조체 채움 바이트는 보지 않는다)
	bool SameState(const FThreatState& A, const FThreatState& B)
	{
		return A.PosX == B.PosX && A.PosY == B.PosY && A.HeadX == B.HeadX && A.HeadY == B.HeadY && A.VelX == B.VelX &&
			   A.VelY == B.VelY && A.Cooldown == B.Cooldown && A.StalkState == B.StalkState && A.StalkLeft == B.StalkLeft &&
			   A.PlayerMode == B.PlayerMode && A.PlayerLeft == B.PlayerLeft && A.bAsleep == B.bAsleep && A.Target == B.Target;
	}

	bool IsKind(int n, std::uint8_t K)
	{
		return kCaseKind[n] == K;
	}

	void Report(const char* Group, int n, const char* Why)
	{
		std::printf("  [%s] 사례 %d (출처 %d,%d,%d%s%s) 어긋남: %s\n", Group, n, kCaseSource[n * 3], kCaseSource[n * 3 + 1],
					kCaseSource[n * 3 + 2], kCaseEdge[n] >= 0 ? ", " : "", kCaseEdge[n] >= 0 ? kEdgeNames[kCaseEdge[n]] : "",
					Why);
	}
}

int main()
{
	int Fail = 0;
	char Why[128];

	// 0. 설정 상수 = 파이썬 설정 (정확히)
	{
		const FThreatConfig Cfg;
		int Bad = 0;
		const double D[][2] = {
			{Cfg.HerbSpeed, kCfgHerbSpeed}, {Cfg.PredViewR, kCfgPredViewR}, {Cfg.PredFovCos, kCfgPredFovCos},
			{Cfg.PredMeleeCatchR, kCfgPredMeleeCatchR}, {Cfg.PredRangedCatchR, kCfgPredRangedCatchR},
			{Cfg.PredRangedCatchP, kCfgPredRangedCatchP}, {Cfg.PredRangedSpeedMult, kCfgPredRangedSpeedMult},
			{Cfg.PredWanderTurn, kCfgPredWanderTurn}, {Cfg.CStill, kCfgCStill}, {Cfg.CoverMultCrouch, kCfgCoverMultCrouch},
			{Cfg.CoverMultGraze, kCfgCoverMultGraze}, {Cfg.CoverMultSleep, kCfgCoverMultSleep},
			{Cfg.CoverMultOther, kCfgCoverMultOther}, {Cfg.SleepDark, kCfgSleepDark}, {Cfg.StalkDist, kCfgStalkDist},
			{Cfg.StalkSpeed, kCfgStalkSpeed}, {Cfg.PounceSpeed, kCfgPounceSpeed}, {Cfg.ExhaustSpeed, kCfgExhaustSpeed},
			{Cfg.PlayerSpeeds[0], kCfgPlayerSpeeds[0]}, {Cfg.PlayerSpeeds[1], kCfgPlayerSpeeds[1]},
			{Cfg.PlayerSpeeds[2], kCfgPlayerSpeeds[2]}, {Cfg.PlayerStalkP, kCfgPlayerStalkP},
			{Cfg.PlayerChargeDist, kCfgPlayerChargeDist}, {Cfg.PlayerCatchR, kCfgPlayerCatchR},
			{Cfg.PredSpeedMultLo, kCfgPredSpeedMultLo}, {Cfg.PredSpeedMultHi, kCfgPredSpeedMultHi},
			{Cfg.RangedFracLo, kCfgRangedFracLo}, {Cfg.RangedFracHi, kCfgRangedFracHi}, {Cfg.StalkFracLo, kCfgStalkFracLo},
			{Cfg.StalkFracHi, kCfgStalkFracHi}, {Cfg.NocturnalFracLo, kCfgNocturnalFracLo},
			{Cfg.NocturnalFracHi, kCfgNocturnalFracHi}, {Cfg.PlayerFrac, kCfgPlayerFrac}, {Cfg.WorldSizeLo, kCfgWorldSizeLo},
			{Cfg.WorldSizeHi, kCfgWorldSizeHi}, {Cfg.Twilight, kCfgTwilight}};
		for (const auto& P : D)
		{
			Bad += P[0] != P[1] ? 1 : 0;
		}
		const long long I[][2] = {
			{Cfg.PredEatCd, kCfgPredEatCd}, {Cfg.PounceSteps, kCfgPounceSteps}, {Cfg.ExhaustSteps, kCfgExhaustSteps},
			{Cfg.PlayerModeStepsLo, kCfgPlayerModeStepsLo}, {Cfg.PlayerModeStepsHi, kCfgPlayerModeStepsHi},
			{Cfg.PlayerChargeSteps, kCfgPlayerChargeSteps}, {Cfg.PlayerRestSteps, kCfgPlayerRestSteps},
			{Cfg.PlayerCooldown, kCfgPlayerCooldown}, {Cfg.PredatorCountLo, kCfgPredatorCountLo},
			{Cfg.PredatorCountHi, kCfgPredatorCountHi}, {Cfg.DayPeriods[0], kCfgDayPeriods[0]},
			{Cfg.DayPeriods[1], kCfgDayPeriods[1]}, {Cfg.DayPeriods[2], kCfgDayPeriods[2]},
			{Cfg.bTwilightSlow ? 1 : 0, kCfgTwilightSlow ? 1 : 0}};
		for (const auto& P : I)
		{
			Bad += P[0] != P[1] ? 1 : 0;
		}
		std::printf("config   mismatch=%d\n", Bad);
		Fail += Bad != 0 ? 1 : 0;
	}

	// 1. 위협 성질 (세계 생성 식)·어둠 d(t) — 사례마다 정확히
	{
		const FThreatConfig Cfg;
		int SpecBad = 0;
		int DarkBad = 0;
		for (int n = 0; n < kCaseCount; ++n)
		{
			const EThreatType Ty = static_cast<EThreatType>(kSpecType[n]);
			const FThreatSpec S = Ty == EThreatType::Player
									  ? MakePlayerSpec(Cfg)
									  : (Ty == EThreatType::Stalker
											 ? MakeStalkerSpec(kSpecSpeedMult[n], kSpecNocturnal[n] != 0, Cfg)
											 : MakeChaserSpec(kSpecSpeedMult[n], kSpecRanged[n] != 0, kSpecNocturnal[n] != 0, Cfg));
			SpecBad += (S.BaseSpeed != kSpecBaseSpeed[n] || S.CatchRadius != kSpecCatchR[n] ||
						S.bRanged != (kSpecRanged[n] != 0) || S.bNocturnal != (kSpecNocturnal[n] != 0))
						   ? 1
						   : 0;
			const double D = DayNightDark(kClock[n * 4], kClock[n * 4 + 1], kClock[n * 4 + 2], kClock[n * 4 + 3]);
			DarkBad += D != kDark[n] ? 1 : 0;
		}
		std::printf("spec     mismatch=%d  daynight mismatch=%d (n=%d)\n", SpecBad, DarkBad, kCaseCount);
		Fail += (SpecBad != 0 || DarkBad != 0) ? 1 : 0;
	}

	// 2. 한 스텝 사례 (본·끝·열의 각 스텝을 골든 입력 상태로 따로)
	{
		const FThreatConfig Cfg;
		const std::uint8_t Kinds[4] = {kKindMain, kKindEdge, kKindSeq, kKindStageSeq};
		const char* Names[4] = {"main", "edge", "seq_step", "stage_step"};
		for (int g = 0; g < 4; ++g)
		{
			double MaxErr = 0.0;
			int Count = 0;
			int Bad = 0;
			for (int n = 0; n < kCaseCount; ++n)
			{
				if (!IsKind(n, Kinds[g]))
				{
					continue;
				}
				++Count;
				FCase C;
				Build(n, C);
				const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
				if (!Compare(n, C.State, R, MaxErr, 0, Why, sizeof(Why)))
				{
					if (Bad < 5)
					{
						Report(Names[g], n, Why);
					}
					++Bad;
				}
			}
			std::printf("%-8s n=%d max_float_err=%.3e mismatch=%d\n", Names[g], Count, MaxErr, Bad);
			Fail += (Bad != 0 || Count == 0) ? 1 : 0;
		}
	}

	// 3. 열: 첫 스텝만 골든 상태, 그 뒤는 C++ 자기 출력 상태를 이어 쓴다
	{
		const FThreatConfig Cfg;
		double MaxErr = 0.0;
		int Bad = 0;
		int Steps = 0;
		for (int s = 0; s < kSeqCount; ++s)
		{
			FThreatState Carry;
			for (int k = 0; k < kSeqLength[s]; ++k)
			{
				const int n = kSeqBegin[s] + k;
				FCase C;
				Build(n, C);
				if (k > 0)
				{
					C.State = Carry;
				}
				const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
				++Steps;
				if (!Compare(n, C.State, R, MaxErr, 0, Why, sizeof(Why)))
				{
					if (Bad < 5)
					{
						std::printf("  [seq %s 스텝 %d] ", kSeqNames[s], k);
						Report("seq", n, Why);
					}
					++Bad;
				}
				Carry = C.State;
			}
		}
		std::printf("chain    seqs=%d steps=%d max_float_err=%.3e mismatch=%d\n", kSeqCount, Steps, MaxErr, Bad);
		Fail += (Bad != 0 || kSeqCount == 0) ? 1 : 0;
	}

	// 4. 문턱 근처 묶음 (보고만 — 실패로 치지 않는다)
	{
		const FThreatConfig Cfg;
		double MaxErr = 0.0;
		int Count = 0;
		int Exact = 0;
		for (int n = 0; n < kCaseCount; ++n)
		{
			if (!IsKind(n, kKindNear))
			{
				continue;
			}
			++Count;
			FCase C;
			Build(n, C);
			const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
			Exact += Compare(n, C.State, R, MaxErr, 0, Why, sizeof(Why)) ? 1 : 0;
		}
		std::printf("near     n=%d exact=%d max_float_err=%.3e (보고만)\n", Count, Exact, MaxErr);
	}

	// 5. 죽은 초식: 앞에 끼운 죽은 초식(위협 바로 앞, 살아 있으면 표적·포획이 되는 자리)은 결과를 바꾸지 않는다. 모두 죽으면 표적·포획이 없다
	{
		const FThreatConfig Cfg;
		double MaxErr = 0.0;
		int Bad = 0;
		int AllDeadBad = 0;
		int Count = 0;
		for (int n = 0; n < kCaseCount; ++n)
		{
			if (!IsKind(n, kKindMain) && !IsKind(n, kKindEdge))
			{
				continue;
			}
			++Count;
			FCase C;
			Build(n, C);
			FPreyView Dead;
			Dead.X = C.State.PosX + 0.25 * C.State.HeadX;
			Dead.Y = C.State.PosY + 0.25 * C.State.HeadY;
			Dead.bAlive = false;
			C.Prey.insert(C.Prey.begin(), Dead);
			C.Roll.insert(C.Roll.begin(), 0.0);
			C.In.Prey = C.Prey.data();
			C.In.NumPrey = static_cast<std::int32_t>(C.Prey.size());
			C.In.RangedRoll = C.Spec.bRanged ? C.Roll.data() : nullptr;
			const FThreatStepResult R = Step(C.Spec, C.State, C.In, Cfg);
			if (!Compare(n, C.State, R, MaxErr, 1, Why, sizeof(Why)))
			{
				if (Bad < 5)
				{
					Report("alive", n, Why);
				}
				++Bad;
			}
			// 모두 죽음 = 초식 없음
			FCase A;
			Build(n, A);
			for (FPreyView& P : A.Prey)
			{
				P.bAlive = false;
			}
			FThreatState B = A.State;
			const FThreatStepResult RA = Step(A.Spec, A.State, A.In, Cfg);
			FThreatStepInput E = A.In;
			E.Prey = nullptr;
			E.NumPrey = 0;
			E.RangedRoll = nullptr;
			const FThreatStepResult RB = Step(A.Spec, B, E, Cfg);
			AllDeadBad += (RA.bHasTarget || RA.Caught >= 0 || !SameState(A.State, B) ||
						   RA.Speed != RB.Speed || RA.bHunting != RB.bHunting)
							  ? 1
							  : 0;
		}
		std::printf("alive    n=%d dead_front_mismatch=%d all_dead_mismatch=%d\n", Count, Bad, AllDeadBad);
		Fail += (Bad != 0 || AllDeadBad != 0) ? 1 : 0;
	}

	// 6. 같은 입력이면 같은 비트 (결정성)
	{
		const FThreatConfig Cfg;
		int Bad = 0;
		for (int n = 0; n < kCaseCount; ++n)
		{
			FCase A;
			FCase B;
			Build(n, A);
			Build(n, B);
			const FThreatStepResult RA = Step(A.Spec, A.State, A.In, Cfg);
			const FThreatStepResult RB = Step(B.Spec, B.State, B.In, Cfg);
			Bad += (!SameState(A.State, B.State) || RA.Speed != RB.Speed ||
					RA.Target != RB.Target || RA.Caught != RB.Caught)
					   ? 1
					   : 0;
		}
		std::printf("determ   mismatch=%d\n", Bad);
		Fail += Bad != 0 ? 1 : 0;
	}

	// 7. 여러 위협이 같은 초식을 잡으면 가장 낮은 위협 색인 (사망 한 번)
	{
		const std::int32_t ByThreat[5] = {2, -1, 0, 2, 7};
		std::int32_t Catcher[4];
		ResolveCatches(ByThreat, 5, Catcher, 4);
		const bool bOk = Catcher[0] == 2 && Catcher[1] == -1 && Catcher[2] == 0 && Catcher[3] == -1;
		std::printf("resolve  %s\n", bOk ? "ok" : "mismatch");
		Fail += bOk ? 0 : 1;
	}

	std::printf(Fail == 0 ? "PASS\n" : "FAIL\n");
	return Fail == 0 ? 0 : 1;
}
