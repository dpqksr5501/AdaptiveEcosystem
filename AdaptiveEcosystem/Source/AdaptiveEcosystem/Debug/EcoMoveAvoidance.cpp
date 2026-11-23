#include "Debug/EcoMoveAvoidance.h"

#if !UE_BUILD_SHIPPING
#include "AI/Policy/EcoLifeLocomotion.h"
#include "Debug/EcoMoveBaseline.h"
#include "HAL/PlatformTime.h"
#include <cstring>

namespace EcoMoveAvoidance
{
	namespace R = EcoRepertoireV3;
	namespace Predict = EcoPredictiveAvoidanceV3;
	using EcoWorldV3::FVec2;

	namespace
	{
		constexpr double Radius = 30. / R::kUnitCm;
		constexpr double ArrivalRadius = .12;
		bool Same(FVec2 A, FVec2 B) { return A.X == B.X && A.Y == B.Y; }
	}

	const TCHAR* Name(EScenario Scenario)
	{
		switch (Scenario)
		{
		case EScenario::HeadOn: return TEXT("HeadOn");
		case EScenario::Crossing: return TEXT("Crossing");
		case EScenario::Graze: return TEXT("Graze");
		case EScenario::Flight: return TEXT("Flight");
		}
		return TEXT("Unknown");
	}

	void FRun::FFixture::Init(EScenario InScenario, int64 Seed, bool bCompare, bool bEnable)
	{
		Scenario = InScenario;
		bCompareApplied = bCompare;
		bEnabled = bEnable;
		EcoWorldV3::FWorldConfig Config;
		Config.Seed = Seed;
		Config.WorldSize = 40.;
		Config.DayPeriod = 0;
		Config.NumHerbivores = 2;
		Config.NumStalkers = Config.NumChasers = Config.NumRanged = Config.NumNocturnal = 0;
		Config.bRespawnDead = false;
		if (bCompareApplied)
		{
			Config.WildFlight.bEnabled = Scenario == EScenario::Flight;
			Config.WorldAllowed[R::kFlee] = Config.WildFlight.bEnabled;
			Config.WorldAllowed[R::kHide] = Config.WorldAllowed[R::kFreeze] = Config.WorldAllowed[R::kSleep] = 0;
			if (Scenario == EScenario::Graze)
			{
				Config.Obstacles.bEnabled = Config.Obstacles.Detour.bEnabled = true;
				Config.Obstacles.Discs = {16., 20.12, .55};
			}
		}
		Native.Init(Config);
		const bool bHeadOn = Scenario == EScenario::HeadOn;
		std::array<FVec2, 2> Starts{{{14., 20.}, bHeadOn ? FVec2{26., 20.} : FVec2{20., 14.}}};
		Goals = {{{28., 20.}, bHeadOn ? FVec2{12., 20.} : FVec2{20., 28.}}};
		if (Scenario == EScenario::Graze || Scenario == EScenario::Flight)
		{
			// Graze meets the stationary deer on the return path from the negative-Y detour.
			Starts[1] = Scenario == EScenario::Graze ? FVec2{20., 19.65} : FVec2{15.6, 20.23};
			Goals[1] = Starts[1];
		}
		if (Scenario == EScenario::Graze)
		{
			// Give the stationary deer a stocked cell in both fixtures, independent of the seed's food patches.
			auto& World = Native.World;
			const auto Cell = World.Food.CellOf(Starts[1]);
			World.Food.Cap[Cell] = World.Food.Food[Cell] = 1.;
			World.Food.ComputeFields(World.ObsCfg.SeeR);
		}
		for (int32 Index = 0; Index < 2; ++Index)
		{
			auto& Body = Native.Bodies[Index];
			Body.Pos = Body.PrevPos = Starts[Index];
			const auto Direction = R::Sub(Goals[Index], Starts[Index]);
			Body.Head = R::IsNonZero(Direction) ? R::Normalize(Direction) : FVec2{1., 0.};
		}
		if (Scenario == EScenario::Flight)
		{
			// Start at the first moving step of an active reflex, after the startle pause.
			R::Enter(Native.Reps[0], R::kFlee, Native.Decisions[0].DecisionObs, Native.World.RepCfg);
			Native.Reps[0].StartleLeft = 0;
			Native.Decisions[0].KeepMode = EcoWorldV3::kKeepPanic;
			Native.Decisions[0].KeepDir = {1., 0.};
		}
		EcoWorldV3::ObserveAndDecideAll(Native.World, Native.Views.data(), Native.NumHerbivores(), nullptr, 0);
	}

	void FRun::FFixture::Control(void* User, int32 Index, const EcoWorldV3::FHerbView& Herb)
	{
		auto& Fixture = *static_cast<FFixture*>(User);
		auto& Move = Fixture.Moves[Index];
		const auto& Config = Fixture.Native.World.RepCfg;
		const auto GoalDelta = R::Sub(Fixture.Goals[Index], Herb.Body->Pos);
		const double Walk = Config.HerbSpeed * Config.GaitSpeed[R::kGaitWalk];
		auto& Control = *Herb.Control;
		if (Fixture.Scenario == EScenario::Flight && Herb.Decision->KeepActive == EcoWorldV3::kKeepPanic)
		{
			Move.Raw = Control.Velocity;
			return;
		}
		Move.Raw = R::ClampMagnitude(GoalDelta, Walk);
		Control.Velocity = Move.Raw;
		const double StopRadius = Fixture.bCompareApplied ? ArrivalRadius : 1.e-6;
		Control.bStill = Fixture.Scenario == EScenario::Flight || R::SizeSquared(GoalDelta) < StopRadius * StopRadius;
		if (Control.bStill) Control.Velocity = Move.Raw = {};
		else
		{
			const FVec2 Other = Fixture.Native.Bodies[1 - Index].Pos;
			const auto Repulsion = EcoLifeMotion::Separation(Herb.Body->Pos, Other, 1., Index + 1, 2 - Index);
			if (R::SizeSquared(Repulsion) > 1.e-8)
				Control.Velocity = EcoLifeMotion::ApplySeparation(Move.Raw, Repulsion, Walk, Herb.Rep->Behavior == R::kGraze);
		}
		Move.Separation = R::Sub(Control.Velocity, Move.Raw);
		Control.Gait = Control.bStill ? R::kGaitStop : R::kGaitWalk;
		Control.DrainMult = Config.GaitDrain[Control.Gait];
		Control.EatMult = Config.GaitEat[Control.Gait];
	}

	bool FRun::FFixture::AllowContact(void* User, int32 Index, const FVec2& From, const FVec2& To)
	{
		auto& Fixture = *static_cast<FFixture*>(User);
		const bool bAllowed = EcoLifeMotion::AllowsMotion(From, To, Fixture.Native.Bodies[1 - Index].Pos, Radius * 2.);
		Fixture.Moves[Index].bContactRejected = !bAllowed;
		return bAllowed;
	}

	void FRun::FFixture::Propose(void* User, const EcoWorldV3::FHerbSteeringRow* Inputs, FVec2* Deltas, int32 Count)
	{
		auto& Fixture = *static_cast<FFixture*>(User);
		std::array<Predict::FAgent, 2> Agents;
		check(Count == static_cast<int32>(Agents.size()));
		for (int32 Index = 0; Index < Count; ++Index)
		{
			const auto& Row = Inputs[Index];
			Agents[Index] = {Index + 1, Row.Position, Row.Delta, Radius, Fixture.Native.Controls[Index].bStill};
		}
		for (int32 Index = 0; Index < Count; ++Index)
		{
			const auto Proposal = Predict::Evaluate(Agents, Index);
			Fixture.Proposals[Index] = Proposal;
			Deltas[Index] = Proposal.Delta;
		}
	}

	void FRun::FFixture::Step(std::vector<EcoWorldV3::FHerbPreMoveRow>* Snapshot)
	{
		Moves = {};
		EcoWorldV3::FStepHooks Hooks;
		Hooks.User = this;
		Hooks.HerbControl = &Control;
		Hooks.HerbMove = &AllowContact;
		Hooks.HerbPreMoveSnapshot = Snapshot;
		if (bCompareApplied)
		{
			MoveObs = {};
			for (int32 Index = 0; Index < 2; ++Index) MoveObs[Index].Index = Index;
			Hooks.HerbMoveObservation = MoveObs.data();
			Hooks.HerbMoveObservationCount = static_cast<int32>(MoveObs.size());
			if (bEnabled) Hooks.HerbAvoidance = &Propose;
		}
		EcoWorldV3::Step(Native.World, Native.Views.data(), Native.NumHerbivores(), nullptr, 0, EcoPolicyV3::kBuiltinNet, &Hooks);
	}

	void FRun::Init(EScenario InScenario, int64 InSeed, int32 Steps, bool bCompareApplied)
	{
		Scenario = InScenario;
		Seed = InSeed;
		bAppliedComparison = bCompareApplied;
		Existing.Init(Scenario, Seed, bCompareApplied, false);
		Shadow.Init(Scenario, Seed, bCompareApplied, true);
		Mismatch = EcoMoveBaseline::CompareNative(Existing.Native, Shadow.Native);
		if (Mismatch) FirstMismatchStep = 0;
		if (bCompareApplied)
		{
			AppliedSamples.Reserve(4 * Steps);
			Off.StepMicros.Reserve(Steps);
			Enabled.StepMicros.Reserve(Steps);
		}
		else Samples.Reserve(Steps);
	}

	void FRun::Step()
	{
		if (bAppliedComparison)
		{
			StepApplied();
			return;
		}
		Existing.Step(nullptr);
		Shadow.Step(&PreMove);
		if (PreMove.size() != Shadow.Native.Bodies.size())
		{
			Mismatch |= EcoMoveBaseline::PreMove;
			if (FirstMismatchStep == INDEX_NONE) FirstMismatchStep = Samples.Num() + 1;
			return;
		}
		FStepSample Sample{};
		Sample.Mismatch = EcoMoveBaseline::CompareNative(Existing.Native, Shadow.Native);
		std::array<Predict::FAgent, 2> Agents;
		for (int32 Index = 0; Index < 2; ++Index)
		{
			const auto& Snapshot = PreMove[Index];
			const auto& Move = Shadow.Moves[Index];
			const auto& Base = Existing.Moves[Index];
			const auto& Body = Shadow.Native.Bodies[Index];
			bTargetDied |= Body.DeathCause != EcoWorldV3::kDeathNone;
			Agents[Index] = {Index + 1, Snapshot.Position, Snapshot.DesiredDelta, Radius, Snapshot.bStill};
			if (Move.bContactRejected != Base.bContactRejected || !Same(Move.Raw, Base.Raw) || !Same(Move.Separation, Base.Separation))
				Sample.Mismatch |= EcoMoveBaseline::Movement;
			if ((Body.DeathCause == EcoWorldV3::kDeathNone && !Same(Snapshot.Position, Body.PrevPos))
				|| !Same(Snapshot.DesiredDelta, Shadow.Native.Controls[Index].Velocity))
				Sample.Mismatch |= EcoMoveBaseline::PreMove;
		}

		auto Proposed = Agents;
		auto Actual = Agents;
		for (int32 Index = 0; Index < 2; ++Index)
		{
			const uint64 Start = FPlatformTime::Cycles64();
			const auto Proposal = Predict::Evaluate(Agents, Index);
			const double Micros = FPlatformTime::ToSeconds64(FPlatformTime::Cycles64() - Start) * 1.e6;
			const auto& Move = Shadow.Moves[Index];
			Proposed[Index].DesiredDelta = Proposal.Delta;
			Actual[Index].DesiredDelta = R::Sub(Shadow.Native.Bodies[Index].Pos, Agents[Index].Position);
			Sample.Deer[Index] = {Samples.Num() + 1, Agents[Index], Shadow.Goals[Index], Move.Raw, Move.Separation,
				PreMove[Index].PreviousDelta, Actual[Index].DesiredDelta, Proposal, Micros, Move.bContactRejected};
			RiskRows += Proposal.RiskId != 0 && Proposal.BaseGap < Predict::GapMargin ? 1 : 0;
			ChangedRows += Proposal.bChanged ? 1 : 0;
			CandidatesDropped += Proposal.Dropped;
			PairChecks += Proposal.PairChecks;
			EvaluationMicros += Micros;
			MaxEvaluationMicros = FMath::Max(MaxEvaluationMicros, Micros);
		}

		Sample.ExistingGap = Predict::ClosestApproach(Agents[0], Agents[0].DesiredDelta, Agents[1], Predict::HorizonSteps).Gap;
		Sample.CombinedProposalGap = Predict::ClosestApproach(Proposed[0], Proposed[0].DesiredDelta, Proposed[1], Predict::HorizonSteps).Gap;
		Sample.ActualGap = Predict::ClosestApproach(Actual[0], Actual[0].DesiredDelta, Actual[1], 1.).Gap;
		JointRegressions += Sample.CombinedProposalGap + 1.e-9 < Sample.ExistingGap ? 1 : 0;
		if (Sample.Mismatch && FirstMismatchStep == INDEX_NONE) FirstMismatchStep = Samples.Num() + 1;
		Mismatch |= Sample.Mismatch;
		Samples.Add(Sample);
	}

	void FRun::StepApplied()
	{
		++CompletedSteps;
		const auto Tick = [this](FFixture& Fixture, FAppliedMetrics& Metrics)
		{
			const uint64 Start = FPlatformTime::Cycles64();
			Fixture.Step(nullptr);
			Metrics.StepMicros.Add(FPlatformTime::ToSeconds64(FPlatformTime::Cycles64() - Start) * 1.e6);
			Measure(Fixture, Metrics);
		};
		Tick(Existing, Off);
		Tick(Shadow, Enabled);
		if (CompletedSteps == 1)
		{
			for (int32 Index = 0; Index < 2; ++Index)
			{
				const auto& A = Existing.Native.Decisions[Index];
				const auto& B = Shadow.Native.Decisions[Index];
				bFirstStepPolicyMatched &= A.ExecutedBehavior == B.ExecutedBehavior && A.CommittedRequest == B.CommittedRequest
					&& std::memcmp(A.CommittedMask, B.CommittedMask, sizeof(A.CommittedMask)) == 0;
			}
		}
		if (Scenario == EScenario::Flight)
		{
			Mismatch |= EcoMoveBaseline::CompareNative(Existing.Native, Shadow.Native);
			if (Mismatch && FirstMismatchStep == INDEX_NONE) FirstMismatchStep = CompletedSteps;
		}
	}

	void FRun::Measure(FFixture& Fixture, FAppliedMetrics& Metrics)
	{
		std::array<Predict::FAgent, 2> Swept;
		for (int32 Index = 0; Index < 2; ++Index)
		{
			const auto& Body = Fixture.Native.Bodies[Index];
			Swept[Index] = {Index + 1, Body.PrevPos, R::Sub(Body.Pos, Body.PrevPos), Radius, false};
		}
		const double Gap = Predict::ClosestApproach(Swept[0], Swept[0].DesiredDelta, Swept[1], 1.).Gap;
		Metrics.Overlaps += Gap < -1.e-6 ? 1 : 0;
		Metrics.FoodEaten = Fixture.Native.World.Stats.FoodEaten;
		for (int32 Index = 0; Index < 2; ++Index)
		{
			const auto& Body = Fixture.Native.Bodies[Index];
			const auto& Decision = Fixture.Native.Decisions[Index];
			const auto& Move = Fixture.MoveObs[Index];
			const auto Proposal = Fixture.bEnabled ? Fixture.Proposals[Index] : Predict::FProposal{Move.AfterTerrain};
			const auto& Actual = Swept[Index].DesiredDelta;
			const bool bStill = Fixture.Native.Controls[Index].bStill;
			const bool bPanic = Decision.KeepActive == EcoWorldV3::kKeepPanic;
			const bool bRejected = Fixture.Moves[Index].bContactRejected;
			const auto Previous = CompletedSteps > 1 ? AppliedSamples[(CompletedSteps - 2) * 4 + (Fixture.bEnabled ? 2 : 0) + Index].Actual : FVec2{};
			const bool bReversal = Previous.X * Actual.X + Previous.Y * Actual.Y < -1.e-9;
			bTargetDied |= Body.DeathCause != EcoWorldV3::kDeathNone;
			ProtectedChanges += (bStill || Decision.KeepActive != EcoWorldV3::kKeepNone || Decision.ExecutedBehavior == R::kFlee)
				&& !Same(Move.AfterTerrain, Move.Final) ? 1 : 0;
			if (bPanic)
			{
				if (Metrics.FirstFlightStep == INDEX_NONE) Metrics.FirstFlightStep = CompletedSteps;
				if (Metrics.FirstFlightMotionStep == INDEX_NONE && R::IsNonZero(Actual)) Metrics.FirstFlightMotionStep = CompletedSteps;
			}
			int32& Arrival = Metrics.ArrivalSteps[Index];
			if (Index < ArrivalTargets() && Arrival == INDEX_NONE
				&& R::SizeSquared(R::Sub(Body.Pos, Fixture.Goals[Index])) < ArrivalRadius * ArrivalRadius)
				Arrival = CompletedSteps;
			Metrics.Reversals += bReversal ? 1 : 0;
			Metrics.AppliedRows += Move.bAvoidanceApplied ? 1 : 0;
			Metrics.ContactRejections += bRejected ? 1 : 0;
			Metrics.DetourRows += Move.bDetourUsed ? 1 : 0;
			Metrics.RiskRows += Proposal.RiskId != 0 && Proposal.BaseGap < Predict::GapMargin ? 1 : 0;
			AppliedSamples.Add({CompletedSteps, Index + 1, Fixture.bEnabled, bStill, Move.bDetourUsed,
				Proposal.bChanged, Move.bAvoidanceApplied, bRejected, bReversal, Decision.ExecutedBehavior, Decision.KeepActive,
				Body.PrevPos, Fixture.Goals[Index], Fixture.Moves[Index].Raw, Fixture.Moves[Index].Separation,
				Move.BeforeDetour, Move.AfterTerrain, Proposal.Delta, Move.Final, Actual,
				Gap, Body.LastIntake, Arrival});
		}
	}

	int32 FRun::ArrivalTargets() const
	{
		if (Scenario == EScenario::Flight) return 0;
		return Scenario == EScenario::Graze ? 1 : 2;
	}

	const TCHAR* FRun::MissingCoverage() const
	{
		if (Scenario == EScenario::Flight)
		{
			const bool bEmergencyProposal = AppliedSamples.ContainsByPredicate([](const FAppliedSample& S)
			{
				return S.bEnabled && S.FlightOverride == EcoWorldV3::kKeepPanic && S.bProposed;
			});
			return Off.FirstFlightMotionStep != INDEX_NONE && bEmergencyProposal ? nullptr : TEXT("EmergencyNotCovered");
		}
		if (Enabled.RiskRows == 0) return TEXT("EncounterNotCovered");
		if (Enabled.AppliedRows == 0) return TEXT("AvoidanceNotApplied");
		if (Scenario == EScenario::Graze)
		{
			if (Off.DetourRows == 0 || Enabled.DetourRows == 0) return TEXT("DetourNotCovered");
			const auto StationaryAte = [this](bool bEnabled)
			{
				return AppliedSamples.ContainsByPredicate([bEnabled](const FAppliedSample& S)
				{
					return S.bEnabled == bEnabled && S.Agent == 2 && S.bStill && S.Intake > 0.;
				});
			};
			if (!StationaryAte(false) || !StationaryAte(true)) return TEXT("StationaryIntakeNotCovered");
		}
		return nullptr;
	}

	const TCHAR* FRun::Regression() const
	{
		if (ProtectedChanges || (Scenario == EScenario::Flight && Mismatch)) return TEXT("ProtectedMovementChanged");
		if (!bFirstStepPolicyMatched || Mismatch) return TEXT("InitialComparisonMismatch");
		if (Enabled.Overlaps > Off.Overlaps) return TEXT("MoreOverlaps");
		for (int32 Index = 0; Index < ArrivalTargets(); ++Index)
			if (Off.ArrivalSteps[Index] != INDEX_NONE && Enabled.ArrivalSteps[Index] == INDEX_NONE) return TEXT("LostArrival");
		if (Scenario == EScenario::Graze && Off.FoodEaten > 0. && Enabled.FoodEaten <= 0.) return TEXT("LostIntake");
		return nullptr;
	}
}
#endif
