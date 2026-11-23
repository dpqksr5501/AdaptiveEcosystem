#pragma once

#if !UE_BUILD_SHIPPING
#include "AI/Policy/EcoPredictiveAvoidanceV3.h"
#include "AI/Policy/EcoWorldV3.h"
#include "CoreMinimal.h"

namespace EcoMoveAvoidance
{
	enum class EScenario : uint8 { HeadOn, Crossing, Graze, Flight };
	const TCHAR* Name(EScenario Scenario);

	struct FSample
	{
		int32 Step;
		EcoPredictiveAvoidanceV3::FAgent Agent;
		EcoWorldV3::FVec2 Goal, Raw, Separation, Previous, Actual;
		EcoPredictiveAvoidanceV3::FProposal Proposal;
		double EvaluationMicros;
		bool bContactRejected;
	};

	struct FStepSample
	{
		std::array<FSample, 2> Deer;
		double ExistingGap, CombinedProposalGap, ActualGap;
		uint32 Mismatch;
	};

	struct FAppliedSample
	{
		int32 Step, Agent;
		bool bEnabled, bStill, bDetour, bProposed, bApplied, bContactRejected, bReversal;
		int32 Behavior, FlightOverride;
		EcoWorldV3::FVec2 Position, Goal, Raw, Separation, BeforeDetour, AfterTerrain, Proposal, Final, Actual;
		double PairGap, Intake;
		int32 ArrivalStep;
	};

	struct FAppliedMetrics
	{
		int32 Reversals = 0, Overlaps = 0, ContactRejections = 0, DetourRows = 0, AppliedRows = 0, RiskRows = 0;
		int32 FirstFlightStep = INDEX_NONE, FirstFlightMotionStep = INDEX_NONE;
		std::array<int32, 2> ArrivalSteps{INDEX_NONE, INDEX_NONE};
		double FoodEaten = 0.;
		TArray<double> StepMicros;
	};

	struct FRun
	{
		EScenario Scenario = EScenario::HeadOn;
		int64 Seed = 0;
		int32 RiskRows = 0, ChangedRows = 0, JointRegressions = 0;
		uint64 CandidatesDropped = 0, PairChecks = 0;
		double EvaluationMicros = 0, MaxEvaluationMicros = 0;
		uint32 Mismatch = 0;
		int32 FirstMismatchStep = INDEX_NONE;
		bool bTargetDied = false;
		TArray<FStepSample> Samples;
		bool bAppliedComparison = false;
		int32 CompletedSteps = 0;
		int32 ProtectedChanges = 0;
		bool bFirstStepPolicyMatched = true;
		FAppliedMetrics Off, Enabled;
		TArray<FAppliedSample> AppliedSamples;

		void Init(EScenario InScenario, int64 InSeed, int32 Steps, bool bCompareApplied = false);
		void Step();
		int32 ArrivalTargets() const;
		const TCHAR* MissingCoverage() const;
		const TCHAR* Regression() const;

	private:
		struct FFixture
		{
			struct FMove
			{
				EcoWorldV3::FVec2 Raw, Separation;
				bool bContactRejected = false;
			};

			EcoWorldV3::FReferenceWorld Native;
			std::array<EcoWorldV3::FVec2, 2> Goals;
			std::array<FMove, 2> Moves;
			std::array<EcoWorldV3::FHerbMoveObservation, 2> MoveObs;
			std::array<EcoPredictiveAvoidanceV3::FProposal, 2> Proposals;
			EScenario Scenario = EScenario::HeadOn;
			bool bCompareApplied = false, bEnabled = false;

			void Init(EScenario InScenario, int64 Seed, bool bCompare, bool bEnable);
			void Step(std::vector<EcoWorldV3::FHerbPreMoveRow>* Snapshot);
			static void Control(void* User, int32 Index, const EcoWorldV3::FHerbView& Herb);
			static bool AllowContact(void* User, int32 Index, const EcoWorldV3::FVec2& From, const EcoWorldV3::FVec2& To);
			static void Propose(void* User, const EcoWorldV3::FHerbSteeringRow* Inputs, EcoWorldV3::FVec2* Deltas, int32 Count);
		};

		void StepApplied();
		void Measure(FFixture& Fixture, FAppliedMetrics& Metrics);
		FFixture Existing, Shadow;
		std::vector<EcoWorldV3::FHerbPreMoveRow> PreMove;
	};
}
#endif
