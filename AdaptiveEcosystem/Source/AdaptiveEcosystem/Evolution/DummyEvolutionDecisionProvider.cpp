// Copyright Epic Games, Inc. All Rights Reserved.

#include "Evolution/EvolutionDecisionProvider.h"
#include "Async/Async.h"
#include "AdaptiveEcosystem.h"

bool UDummyEvolutionDecisionProvider::RequestProposal_Implementation(const FEvolutionContext& Context, FEvolutionProposal& OutProposal)
{
	OutProposal = FEvolutionProposal();

	OutProposal.WorldEpoch = Context.WorldEpoch;
	OutProposal.ContextRevision = Context.ContextRevision;
	OutProposal.ModelRevision = 1;
	OutProposal.SchemaRevision = 1;

	// Simple heuristic fallback:
	// If hunting pressure is high, evolve towards higher fear, higher move speed, and smaller body scale.
	if (Context.Pressure.HuntingPressure > 0.5f)
	{
		OutProposal.FearDelta = 0.05f;
		OutProposal.MoveSpeedDelta = 0.03f;
		OutProposal.BodyScaleDelta = -0.02f;
		OutProposal.AggressionDelta = -0.04f;
	}
	else
	{
		// Baseline subtle shift
		OutProposal.FearDelta = 0.01f;
		OutProposal.MoveSpeedDelta = 0.01f;
		OutProposal.BodyScaleDelta = 0.0f;
		OutProposal.AggressionDelta = 0.01f;
	}

	// Ecological feedback: if FoodAvailability is low (< 0.4f), adapt to food scarcity by reducing body scale
	// (lower metabolic footprint) and increasing roam radius and move speed to forage over broader areas.
	if (Context.Environment.FoodAvailability < 0.4f)
	{
		OutProposal.BodyScaleDelta -= 0.03f;
		OutProposal.RoamRadiusDelta += 0.05f;
		OutProposal.MoveSpeedDelta += 0.02f;
	}
	else if (Context.Environment.FoodAvailability > 0.75f)
	{
		// Food abundance supports larger physical frame
		OutProposal.BodyScaleDelta += 0.02f;
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("DummyEvolutionDecisionProvider: Created proposal for [%s x %s] (FearDelta: %.2f, SpeedDelta: %.2f, ScaleDelta: %.2f, RoamDelta: %.2f)"),
		*Context.RegionId.ToString(), *Context.SpeciesId.ToString(),
		OutProposal.FearDelta, OutProposal.MoveSpeedDelta, OutProposal.BodyScaleDelta, OutProposal.RoamRadiusDelta);

	return true;
}

bool UDummyEvolutionDecisionProvider::RequestVegetationProposal(const FVegetationEvolutionContext& Context, FVegetationEvolutionProposal& OutProposal)
{
	OutProposal = FVegetationEvolutionProposal();

	OutProposal.WorldEpoch = Context.WorldEpoch;
	OutProposal.ContextRevision = Context.ContextRevision;
	OutProposal.ModelRevision = 1;
	OutProposal.SchemaRevision = 1;

	// Heuristic vegetation adaptation:
	// If grazing pressure is high, evolve towards higher grazing resistance and faster regeneration.
	if (Context.GrazingPressure > 0.5f)
	{
		OutProposal.GrazingResistanceDelta = 0.06f;
		OutProposal.RegenerationRateDelta = 0.04f;
		OutProposal.GrowthRateDelta = -0.02f;
	}
	else if (Context.HarvestPressure > 0.5f)
	{
		OutProposal.GrazingResistanceDelta = 0.02f;
		OutProposal.RegenerationRateDelta = 0.05f;
		OutProposal.GrowthRateDelta = 0.02f;
	}
	else
	{
		// Gentle baseline drift
		OutProposal.GrowthRateDelta = 0.01f;
		OutProposal.RegenerationRateDelta = 0.01f;
		OutProposal.GrazingResistanceDelta = 0.01f;
	}

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("DummyEvolutionDecisionProvider (Vegetation): Created proposal for [%s x %s] (GrowthDelta: %.2f, RegenDelta: %.2f, ResistDelta: %.2f)"),
		*Context.RegionId.ToString(), *Context.VegetationSpeciesId.ToString(),
		OutProposal.GrowthRateDelta, OutProposal.RegenerationRateDelta, OutProposal.GrazingResistanceDelta);

	return true;
}

void UDummyEvolutionDecisionProvider::RequestProposalAsync(
	const FEvolutionContext& Context,
	FOnEvolutionProposalCompleted OnCompleted)
{
	// Asynchronously execute proposal creation on a worker thread to guarantee zero Game Thread blocking
	AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, [Context, OnCompleted]()
	{
		// Simulate background task dispatch latency
		FPlatformProcess::Sleep(0.01f);

		FEvolutionProposal Proposal;
		UDummyEvolutionDecisionProvider DummyProvider;
		const bool bSuccess = DummyProvider.RequestProposal_Implementation(Context, Proposal);

		// Safely dispatch the generated proposal back to the Game Thread for server validation and commit
		AsyncTask(ENamedThreads::GameThread, [OnCompleted, bSuccess, Proposal]()
		{
			OnCompleted.ExecuteIfBound(bSuccess, Proposal);
		});
	});
}

void UDummyEvolutionDecisionProvider::RequestVegetationProposalAsync(
	const FVegetationEvolutionContext& Context,
	FOnVegetationEvolutionProposalCompleted OnCompleted)
{
	// Asynchronously execute vegetation proposal creation on a worker thread
	AsyncTask(ENamedThreads::AnyBackgroundThreadNormalTask, [Context, OnCompleted]()
	{
		// Simulate background task dispatch latency
		FPlatformProcess::Sleep(0.01f);

		FVegetationEvolutionProposal Proposal;
		const bool bSuccess = RequestVegetationProposal(Context, Proposal);

		// Safely dispatch the generated proposal back to the Game Thread for server validation and commit
		AsyncTask(ENamedThreads::GameThread, [OnCompleted, bSuccess, Proposal]()
		{
			OnCompleted.ExecuteIfBound(bSuccess, Proposal);
		});
	});
}
