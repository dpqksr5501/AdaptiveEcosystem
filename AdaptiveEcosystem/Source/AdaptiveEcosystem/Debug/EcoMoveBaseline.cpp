#include "Debug/EcoMoveBaseline.h"

#if !UE_BUILD_SHIPPING
namespace EcoMoveBaseline
{
	namespace
	{
		using namespace EcoWorldV3;

		bool Same(FVec2 A, FVec2 B)
		{
			return A.X == B.X && A.Y == B.Y;
		}

		template<typename T, size_t N>
		bool SameBits(const T (&A)[N], const T (&B)[N])
		{
			return FMemory::Memcmp(A, B, sizeof(A)) == 0;
		}
	}

	using EcoWorldV3::FReferenceWorld;

	uint32 CompareNative(const FReferenceWorld& A, const FReferenceWorld& B)
	{
		uint32 Flags = 0;
		const auto& X = A.World;
		const auto& Y = B.World;
		if (X.Rng.State != Y.Rng.State) Flags |= Random;
		if (X.T != Y.T || X.Food.Food != Y.Food.Food || X.Food.Cap != Y.Food.Cap || X.Food.Regen != Y.Food.Regen
			|| X.PredEma != Y.PredEma || X.Stats.FoodEaten != Y.Stats.FoodEaten || X.Stats.EatSteps != Y.Stats.EatSteps
			|| X.Stats.Caught != Y.Stats.Caught || X.Stats.Starved != Y.Stats.Starved || X.Stats.Reproduced != Y.Stats.Reproduced)
			Flags |= Ledger;

		for (int32 Index = 0; Index < A.NumHerbivores(); ++Index)
		{
			const auto& P = A.Perceptions[Index];
			const auto& Q = B.Perceptions[Index];
			if (P.Kin.KinCount != Q.Kin.KinCount || P.Kin.FleeCount != Q.Kin.FleeCount || P.Kin.KinAlarm != Q.Kin.KinAlarm
				|| !Same(P.Kin.ToCentroid, Q.Kin.ToCentroid) || !Same(P.Kin.Separation, Q.Kin.Separation))
				Flags |= Kin;
			if (!SameBits(P.Obs, Q.Obs) || !SameBits(P.ObstacleObs, Q.ObstacleObs) || !SameBits(P.RouteObs, Q.RouteObs))
				Flags |= Observation;

			const auto& D = A.Decisions[Index];
			const auto& E = B.Decisions[Index];
			const auto& R = A.Reps[Index];
			const auto& S = B.Reps[Index];
			if (!SameBits(D.Mask, E.Mask) || !SameBits(D.CommittedMask, E.CommittedMask)
				|| !SameBits(D.Logits, E.Logits) || D.Request != E.Request || D.CommittedRequest != E.CommittedRequest
				|| D.ExecutedBehavior != E.ExecutedBehavior || D.bCommittedReads != E.bCommittedReads
				|| D.KeepMode != E.KeepMode || D.KeepActive != E.KeepActive
				|| R.Behavior != S.Behavior || R.Phase != S.Phase || R.HideTarget != S.HideTarget || R.bArrived != S.bArrived)
				Flags |= Decision;

			const auto& BodyA = A.Bodies[Index];
			const auto& BodyB = B.Bodies[Index];
			if (!Same(BodyA.Pos, BodyB.Pos) || !Same(BodyA.Head, BodyB.Head)
				|| !Same(BodyA.PrevPos, BodyB.PrevPos) || !Same(A.Controls[Index].Velocity, B.Controls[Index].Velocity))
				Flags |= Movement;
			if (BodyA.Energy != BodyB.Energy || BodyA.LastIntake != BodyB.LastIntake || BodyA.DeathCause != BodyB.DeathCause
				|| BodyA.CaughtBy != BodyB.CaughtBy || BodyA.Generation != BodyB.Generation
				|| BodyA.bReproduced != BodyB.bReproduced || BodyA.bRespawned != BodyB.bRespawned)
				Flags |= Ledger;
		}

		for (int32 Index = 0; Index < A.NumThreats(); ++Index)
		{
			const auto& W = A.Threats[Index];
			const auto& V = B.Threats[Index];
			if (W.State.PosX != V.State.PosX || W.State.PosY != V.State.PosY || W.State.VelX != V.State.VelX || W.State.VelY != V.State.VelY)
				Flags |= Movement;
			if (W.Last.Caught != V.Last.Caught || W.Last.Target != V.Last.Target || W.State.Target != V.State.Target
				|| W.State.Cooldown != V.State.Cooldown)
				Flags |= Ledger;
		}
		return Flags;
	}

	namespace
	{
		using namespace EcoWorldV3;

		FStepReport StepWithSnapshot(FReferenceWorld& Ref, std::vector<FHerbPreMoveRow>& Snapshot, std::vector<FVec2>& Start)
		{
			for (int32 Index = 0; Index < Ref.NumHerbivores(); ++Index) Start[Index] = Ref.Bodies[Index].Pos;
			FStepHooks Hooks;
			Hooks.HerbPreMoveSnapshot = &Snapshot;
			return EcoWorldV3::Step(Ref.World, Ref.Views.data(), Ref.NumHerbivores(), Ref.ThreatPtrs.data(),
				Ref.NumThreats(), EcoPolicyV3::kBuiltinNet, &Hooks);
		}
	}

	void FPair::Init(int64 Seed, int32 Deer, double WorldSize, int32 Steps)
	{
		EcoWorldV3::FWorldConfig Config;
		Config.Seed = Seed;
		Config.NumHerbivores = Deer;
		Config.WorldSize = WorldSize;
		Config.NumStalkers = 2;
		Config.NumChasers = 2;
		Config.NumRanged = Config.NumNocturnal = 0;
		Config.RealismHearing.bEnabled = true;
		Config.WildFlight.bEnabled = true;
		Config.Covers = EcoWorldV3::QuadCovers(WorldSize, 7.);
		Full.Init(Config, false);
		Spatial.Init(Config, true);
		FullStart.resize(Deer);
		SpatialStart.resize(Deer);
		Rows.Reserve(Steps + 1);
		Full.World.SearchDiagnostics.bEnabled = true;
		Spatial.World.SearchDiagnostics.bEnabled = true;
		Add({0, CompareNative(Full, Spatial)});
	}

	void FPair::Step()
	{
		Full.World.SearchDiagnostics.Reset();
		Spatial.World.SearchDiagnostics.Reset();
		const auto A = StepWithSnapshot(Full, FullSnapshot, FullStart);
		const auto B = StepWithSnapshot(Spatial, SpatialSnapshot, SpatialStart);
		uint32 Flags = CompareNative(Full, Spatial);
		if (A.Caught != B.Caught || A.Starved != B.Starved || A.Reproduced != B.Reproduced || A.Respawned != B.Respawned)
			Flags |= Ledger;

		if (FullSnapshot.size() != FullStart.size() || SpatialSnapshot.size() != SpatialStart.size()
			|| FullSnapshot.size() != SpatialSnapshot.size())
			Flags |= PreMove;
		else
		{
			for (size_t Index = 0; Index < FullSnapshot.size(); ++Index)
			{
				const auto& X = FullSnapshot[Index];
				const auto& Y = SpatialSnapshot[Index];
				if (!Same(X.Position, FullStart[Index]) || !Same(Y.Position, SpatialStart[Index]) || !Same(X.Position, Y.Position)
					|| !Same(X.Heading, Y.Heading) || !Same(X.PreviousDelta, Y.PreviousDelta) || !Same(X.DesiredDelta, Y.DesiredDelta)
					// This fixture has no detour or shore steer, so controls retain the pre-move delta.
					|| !Same(X.DesiredDelta, Full.Controls[Index].Velocity) || !Same(Y.DesiredDelta, Spatial.Controls[Index].Velocity)
					|| X.Behavior != Y.Behavior || X.FlightOverride != Y.FlightOverride || X.Gait != Y.Gait || X.bStill != Y.bStill)
					Flags |= PreMove;
			}
		}

		const auto& Scan = Full.World.SearchDiagnostics.Kin;
		const auto& Grid = Spatial.World.SearchDiagnostics.Kin;
		if (Scan.Calls != Grid.Calls || Scan.FullCandidates != Grid.FullCandidates || Scan.Candidates != Scan.FullCandidates
			|| Grid.Candidates > Scan.Candidates)
			Flags |= Kin;
		Add({Full.World.Stats.Steps, Flags, Scan.Candidates, Grid.Candidates, Grid.Calls, int32(SpatialSnapshot.size())});
	}

	void FPair::Add(FRow Row)
	{
		if (Row.Mismatch && FirstMismatchStep < 0) FirstMismatchStep = Row.Step;
		Mismatch |= Row.Mismatch;
		FullCandidates += Row.FullCandidates;
		SpatialCandidates += Row.SpatialCandidates;
		Queries += Row.Queries;
		Rows.Add(Row);
	}

	void FRun::Init(int64 InSeed, int32 Steps)
	{
		Seed = InSeed;
		Sparse.Init(Seed, SparseDeer, 200., Steps);
		Small.Init(Seed, SmallDeer, 60., Steps);
	}

	void FRun::Step()
	{
		Sparse.Step();
		Small.Step();
		++Completed;
	}
}
#endif
