// Copyright Epic Games, Inc. All Rights Reserved.

#include "Evolution/EvolutionDecisionProvider.h"
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

	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("DummyEvolutionDecisionProvider: Created proposal for [%s x %s] (FearDelta: %.2f, SpeedDelta: %.2f, ScaleDelta: %.2f)"),
		*Context.RegionId.ToString(), *Context.SpeciesId.ToString(),
		OutProposal.FearDelta, OutProposal.MoveSpeedDelta, OutProposal.BodyScaleDelta);

	return true;
}
